/// <reference lib="deno.ns" />
/// <reference lib="deno.unstable" />

import { Application, Router, send, type Context } from "@oak/oak";
import { ensureDir, walk } from "@std/fs";
import { basename, extname, join, normalize } from "@std/path";

type ConversionTarget = "vault_md" | "vault_json" | "docx" | "html" | "pdf";
type SourceType = "auto" | "ppt" | "word" | "generic";
type EffectiveSourceType = "ppt" | "word" | "generic";
type FileStatus = "queued" | "uploading" | "converting" | "completed" | "failed";

interface SSEConnection {
  conversionId: string;
  controller: ReadableStreamDefaultController;
  lastActivity: number;
}

interface ProgressEvent {
  type: "progress";
  progress: number;
  current: number;
  total: number;
  message: string;
}

interface AppConfig {
  port: number;
  bindHost: string;
  uploadDir: string;
  outputDir: string;
  vaultOutputDir: string;
  maxConcurrentConversions: number;
  maxFileSizeBytes: number;
  maxFilesPerRequest: number;
  uploadRetentionMinutes: number;
  logLevel: string;
}

interface ConversionError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  retryable: boolean;
}

interface ConversionResult {
  inputName: string;
  storedUploadName: string;
  target: ConversionTarget;
  sourceType: EffectiveSourceType;
  status: FileStatus;
  outputFileName: string | null;
  outputPath: string | null;
  downloadUrl: string | null;
  durationMs: number;
  error: ConversionError | null;
  conversionId?: string;
}

interface PythonSuccessPayload {
  status: "completed";
  outputPath: string;
  sourceType?: EffectiveSourceType;
  pagesProcessed?: number;
  imagesDetected?: number;
  durationMs?: number;
}

class Semaphore {
  private available: number;
  private queue: Array<() => void> = [];

  constructor(limit: number) {
    this.available = limit;
  }

  async acquire(): Promise<() => void> {
    if (this.available > 0) {
      this.available -= 1;
      return () => this.release();
    }

    await new Promise<void>((resolve) => this.queue.push(resolve));
    this.available -= 1;
    return () => this.release();
  }

  private release() {
    this.available += 1;
    const next = this.queue.shift();
    if (next) {
      next();
    }
  }
}

const config: AppConfig = {
  port: Number(Deno.env.get("PORT") ?? "7482"),
  bindHost: Deno.env.get("MARKDONE_BIND_HOST") ?? "0.0.0.0",
  uploadDir: Deno.env.get("UPLOAD_DIR") ?? "/app/uploads",
  outputDir: Deno.env.get("OUTPUT_DIR") ?? "/app/outputs",
  vaultOutputDir: Deno.env.get("VAULT_OUTPUT_DIR") ?? "/app/outputs/vault",
  maxConcurrentConversions: Number(Deno.env.get("MAX_CONCURRENT_CONVERSIONS") ?? "4"),
  maxFileSizeBytes: Number(Deno.env.get("MAX_FILE_SIZE_MB") ?? "100") * 1024 * 1024,
  maxFilesPerRequest: Number(Deno.env.get("MAX_FILES_PER_REQUEST") ?? "20"),
  uploadRetentionMinutes: Number(Deno.env.get("UPLOAD_RETENTION_MINUTES") ?? "10"),
  logLevel: Deno.env.get("LOG_LEVEL") ?? "info",
};

const app = new Application();
const router = new Router();
const semaphore = new Semaphore(config.maxConcurrentConversions);
const startedAt = Date.now();
let shuttingDown = false;
let activeConversions = 0;
const activeProcesses = new Set<Deno.ChildProcess>();

// SSE connection management
const sseConnections = new Map<string, SSEConnection>();

function relayProgressToSSE(conversionId: string, data: ProgressEvent) {
  const connection = sseConnections.get(conversionId);
  if (connection) {
    const encoder = new TextEncoder();
    const message = `event: progress\ndata: ${JSON.stringify(data)}\n\n`;
    try {
      connection.controller.enqueue(encoder.encode(message));
      connection.lastActivity = Date.now();
    } catch {
      // Connection closed, remove it
      sseConnections.delete(conversionId);
    }
  }
}

function sendSSEComplete(conversionId: string, data: Record<string, unknown>) {
  const connection = sseConnections.get(conversionId);
  if (connection) {
    const encoder = new TextEncoder();
    const message = `event: complete\ndata: ${JSON.stringify(data)}\n\n`;
    try {
      connection.controller.enqueue(encoder.encode(message));
      connection.controller.close();
    } catch {
      // Ignore errors on close
    }
    sseConnections.delete(conversionId);
  }
}

function sendSSEError(conversionId: string, error: ConversionError) {
  const connection = sseConnections.get(conversionId);
  if (connection) {
    const encoder = new TextEncoder();
    const message = `event: error\ndata: ${JSON.stringify(error)}\n\n`;
    try {
      connection.controller.enqueue(encoder.encode(message));
      connection.controller.close();
    } catch {
      // Ignore errors on close
    }
    sseConnections.delete(conversionId);
  }
}

function createError(
  code: string,
  message: string,
  details: Record<string, unknown> = {},
  retryable = false,
): ConversionError {
  return { code, message, details, retryable };
}

function sanitizeBaseName(fileName: string): string {
  const withoutExt = basename(fileName, extname(fileName));
  const sanitized = withoutExt
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return sanitized || "document";
}

function safeOutputName(fileName: string, extension: string): string {
  return `${sanitizeBaseName(fileName)}${extension}`;
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await Deno.stat(path);
    return true;
  } catch {
    return false;
  }
}

async function uniqueOutputPath(directory: string, fileName: string): Promise<string> {
  const extension = extname(fileName);
  const stem = basename(fileName, extension);
  let candidate = join(directory, fileName);
  let counter = 1;

  while (await pathExists(candidate)) {
    candidate = join(directory, `${stem}-${counter}${extension}`);
    counter += 1;
  }

  return candidate;
}

function isValidTarget(value: string): value is ConversionTarget {
  return ["vault_md", "vault_json", "docx", "html", "pdf"].includes(value);
}

function isValidSourceType(value: string): value is SourceType {
  return ["auto", "ppt", "word", "generic"].includes(value);
}

function parseBoolean(value: string | null): boolean | null {
  if (value === null || value === "") {
    return null;
  }

  const normalized = value.toLowerCase();
  if (["true", "1", "yes", "on"].includes(normalized)) {
    return true;
  }
  if (["false", "0", "no", "off"].includes(normalized)) {
    return false;
  }
  return null;
}

function normalizeSourceType(sourceType: SourceType): EffectiveSourceType {
  return sourceType === "auto" ? "word" : sourceType;
}

async function checkDependency(command: string, args: string[]): Promise<boolean> {
  try {
    const proc = new Deno.Command(command, {
      args,
      stdout: "null",
      stderr: "null",
    }).spawn();
    const status = await proc.status;
    return status.success;
  } catch {
    return false;
  }
}

async function ensureDirectories() {
  await ensureDir(config.uploadDir);
  await ensureDir(config.outputDir);
  await ensureDir(config.vaultOutputDir);
}

async function cleanupUploads() {
  for await (const entry of walk(config.uploadDir, { includeDirs: false, maxDepth: 1 })) {
    try {
      const stat = await Deno.stat(entry.path);
      const cutoff = Date.now() - (config.uploadRetentionMinutes * 60 * 1000);
      if ((stat.mtime?.getTime() ?? Date.now()) < cutoff) {
        await Deno.remove(entry.path);
      }
    } catch {
      // ignore cleanup errors
    }
  }
}

function buildDownloadUrl(outputFileName: string | null): string | null {
  return outputFileName ? `/api/downloads/${encodeURIComponent(outputFileName)}` : null;
}

async function runPythonConversion(
  inputPath: string,
  outputPath: string,
  sourceType: SourceType,
  yamlFrontmatter: boolean,
  conversionId?: string,
): Promise<{ sourceType: EffectiveSourceType; durationMs: number }> {
  const release = await semaphore.acquire();
  activeConversions += 1;
  const started = Date.now();

  try {
    const proc = new Deno.Command("python3", {
      args: [
        "services/high_fidelity_pdf.py",
        "--input",
        inputPath,
        "--output",
        outputPath,
        "--source-type",
        sourceType,
        "--yaml-frontmatter",
        String(yamlFrontmatter),
      ],
      stdout: "piped",
      stderr: "piped",
      cwd: Deno.cwd(),
    }).spawn();

    activeProcesses.add(proc);

    // Collect both stdout and stderr
    const stdoutChunks: Uint8Array[] = [];
    const stderrChunks: Uint8Array[] = [];
    const decoder = new TextDecoder();
    
    // Stream stdout
    const stdoutPromise = (async () => {
      const reader = proc.stdout.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          stdoutChunks.push(value);
        }
      } catch {
        // Stream closed or error, ignore
      }
    })();
    
    // Stream stderr for progress updates
    const stderrPromise = (async () => {
      const reader = proc.stderr.getReader();
      let buffer = "";
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          // Collect chunks for later
          stderrChunks.push(value);
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          
          for (const line of lines) {
            if (line.trim()) {
              try {
                const data = JSON.parse(line);
                if (data.type === "progress" && conversionId) {
                  relayProgressToSSE(conversionId, data as ProgressEvent);
                }
              } catch {
                // Not JSON progress event, ignore
              }
            }
          }
        }
      } catch {
        // Stream closed or error, ignore
      }
    })();

    // Wait for process to complete and all streams to finish
    const [status] = await Promise.all([
      proc.status,
      stdoutPromise,
      stderrPromise,
    ]);
    
    activeProcesses.delete(proc);

    if (!status.success) {
      // Reconstruct stderr from collected chunks
      const totalLength = stderrChunks.reduce((acc, chunk) => acc + chunk.length, 0);
      const stderrData = new Uint8Array(totalLength);
      let offset = 0;
      for (const chunk of stderrChunks) {
        stderrData.set(chunk, offset);
        offset += chunk.length;
      }
      const message = new TextDecoder().decode(stderrData).trim() || "High-fidelity conversion failed";
      throw new Error(message);
    }

    // Reconstruct stdout from collected chunks
    const stdoutLength = stdoutChunks.reduce((acc, chunk) => acc + chunk.length, 0);
    const stdoutData = new Uint8Array(stdoutLength);
    let stdoutOffset = 0;
    for (const chunk of stdoutChunks) {
      stdoutData.set(chunk, stdoutOffset);
      stdoutOffset += chunk.length;
    }
    
    const payload = JSON.parse(new TextDecoder().decode(stdoutData).trim()) as PythonSuccessPayload;
    return {
      sourceType: payload.sourceType ?? normalizeSourceType(sourceType),
      durationMs: payload.durationMs ?? (Date.now() - started),
    };
  } finally {
    activeConversions -= 1;
    release();
  }
}

async function runPandocConversion(inputPath: string, outputPath: string): Promise<number> {
  const release = await semaphore.acquire();
  activeConversions += 1;
  const started = Date.now();

  try {
    const pandocArgs = [inputPath, "-o", outputPath];
    // Use weasyprint as PDF engine (no LaTeX required)
    if (extname(outputPath).toLowerCase() === ".pdf") {
      pandocArgs.push("--pdf-engine=weasyprint");
    }

    const proc = new Deno.Command("pandoc", {
      args: pandocArgs,
      stdout: "null",
      stderr: "piped",
      cwd: Deno.cwd(),
    }).spawn();

    activeProcesses.add(proc);
    const output = await proc.output();
    activeProcesses.delete(proc);

    if (!output.success) {
      const message = new TextDecoder().decode(output.stderr).trim() || "Pandoc conversion failed";
      throw new Error(message);
    }

    return Date.now() - started;
  } finally {
    activeConversions -= 1;
    release();
  }
}

async function runXlsxConversion(
  inputPath: string,
  outputPath: string,
  target: "vault_md" | "vault_json",
  yamlFrontmatter: boolean,
  conversionId?: string,
): Promise<{ sheetsProcessed: number; rowsProcessed: number; durationMs: number }> {
  const release = await semaphore.acquire();
  activeConversions += 1;
  const started = Date.now();

  try {
    const proc = new Deno.Command("python3", {
      args: [
        "services/xlsx_converter.py",
        "--input",
        inputPath,
        "--output",
        outputPath,
        "--target",
        target,
        "--yaml-frontmatter",
        String(yamlFrontmatter),
      ],
      stdout: "piped",
      stderr: "piped",
      cwd: Deno.cwd(),
    }).spawn();

    activeProcesses.add(proc);

    // Collect both stdout and stderr
    const stdoutChunks: Uint8Array[] = [];
    const stderrChunks: Uint8Array[] = [];
    const decoder = new TextDecoder();
    
    // Stream stdout
    const stdoutPromise = (async () => {
      const reader = proc.stdout.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          stdoutChunks.push(value);
        }
      } catch {
        // Stream closed or error, ignore
      }
    })();
    
    // Stream stderr for progress updates
    const stderrPromise = (async () => {
      const reader = proc.stderr.getReader();
      let buffer = "";
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          // Collect chunks for later
          stderrChunks.push(value);
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          
          for (const line of lines) {
            if (line.trim()) {
              try {
                const data = JSON.parse(line);
                if (data.type === "progress" && conversionId) {
                  relayProgressToSSE(conversionId, data as ProgressEvent);
                }
              } catch {
                // Not JSON progress event, ignore
              }
            }
          }
        }
      } catch {
        // Stream closed or error, ignore
      }
    })();

    // Wait for process to complete and all streams to finish
    const [status] = await Promise.all([
      proc.status,
      stdoutPromise,
      stderrPromise,
    ]);
    
    activeProcesses.delete(proc);

    if (!status.success) {
      // Reconstruct stderr from collected chunks
      const totalLength = stderrChunks.reduce((acc, chunk) => acc + chunk.length, 0);
      const stderrData = new Uint8Array(totalLength);
      let offset = 0;
      for (const chunk of stderrChunks) {
        stderrData.set(chunk, offset);
        offset += chunk.length;
      }
      const message = new TextDecoder().decode(stderrData).trim() || "XLSX conversion failed";
      throw new Error(message);
    }

    // Reconstruct stdout from collected chunks
    const stdoutLength = stdoutChunks.reduce((acc, chunk) => acc + chunk.length, 0);
    const stdoutData = new Uint8Array(stdoutLength);
    let stdoutOffset = 0;
    for (const chunk of stdoutChunks) {
      stdoutData.set(chunk, stdoutOffset);
      stdoutOffset += chunk.length;
    }
    
    const payload = JSON.parse(new TextDecoder().decode(stdoutData).trim());
    return {
      sheetsProcessed: payload.sheetsProcessed ?? 0,
      rowsProcessed: payload.rowsProcessed ?? 0,
      durationMs: payload.durationMs ?? (Date.now() - started),
    };
  } finally {
    activeConversions -= 1;
    release();
  }
}

async function persistUploadedFile(part: File, storedName: string): Promise<string> {
  const outputPath = join(config.uploadDir, storedName);
  const arrayBuffer = await part.arrayBuffer();

  if (arrayBuffer.byteLength > config.maxFileSizeBytes) {
    throw createError(
      "FILE_TOO_LARGE",
      "File exceeds configured size limit",
      {
        fileName: part.name,
        maxFileSizeBytes: config.maxFileSizeBytes,
      },
      false,
    );
  }

  await Deno.writeFile(outputPath, new Uint8Array(arrayBuffer));
  return outputPath;
}

router.get("/health", async (ctx: Context) => {
  const [pandocOk, pythonOk] = await Promise.all([
    checkDependency("pandoc", ["--version"]),
    checkDependency("python3", ["--version"]),
  ]);

  ctx.response.body = {
    status: pandocOk && pythonOk ? "ok" : "degraded",
    service: "markdone",
    version: "1.0.0",
    dependencies: {
      pandoc: pandocOk,
      python3: pythonOk,
    },
    supportedInputs: ["pdf", "md", "xlsx", "xlsm"],
    supportedTargets: ["vault_md", "vault_json", "docx", "html", "pdf"],
    uptimeSeconds: Math.floor((Date.now() - startedAt) / 1000),
    concurrency: {
      limit: config.maxConcurrentConversions,
      active: activeConversions,
    },
  };
});

router.get("/api/convert/progress/:conversionId", (ctx: Context) => {
  const conversionId = ctx.params.conversionId;
  
  if (!conversionId) {
    ctx.response.status = 400;
    ctx.response.body = createError("INVALID_REQUEST", "Missing conversionId", {}, false);
    return;
  }

  const stream = new ReadableStream({
    start(controller) {
      sseConnections.set(conversionId, {
        conversionId,
        controller,
        lastActivity: Date.now(),
      });
      
      // Send initial connection event
      const encoder = new TextEncoder();
      controller.enqueue(encoder.encode("event: connected\ndata: {}\n\n"));
    },
    cancel() {
      sseConnections.delete(conversionId);
    },
  });
  
  ctx.response.headers.set("Content-Type", "text/event-stream");
  ctx.response.headers.set("Cache-Control", "no-cache");
  ctx.response.headers.set("Connection", "keep-alive");
  ctx.response.headers.set("X-Accel-Buffering", "no"); // Disable nginx buffering
  ctx.response.body = stream;
});

router.get("/api/downloads/:fileName", async (ctx: Context) => {
  const fileName = ctx.params.fileName ? decodeURIComponent(ctx.params.fileName) : "";
  if (!fileName || fileName.includes("/") || fileName.includes("..")) {
    ctx.response.status = 400;
    ctx.response.body = createError("INVALID_REQUEST", "Invalid download path", {}, false);
    return;
  }

  // Try vault output dir first, then general output dir
  const vaultPath = join(config.vaultOutputDir, fileName);
  if (await pathExists(vaultPath)) {
    await send(ctx, fileName, {
      root: normalize(config.vaultOutputDir),
    });
    return;
  }

  await send(ctx, fileName, {
    root: normalize(config.outputDir),
  });
});

router.get("/api/outputs", async (ctx: Context) => {
  const files: Array<{ name: string; size: number; downloadUrl: string; modifiedAt: string }> = [];

  for (const dir of [config.vaultOutputDir, config.outputDir]) {
    try {
      for await (const entry of walk(dir, { includeDirs: false, maxDepth: 1 })) {
        const stat = await Deno.stat(entry.path);
        const name = basename(entry.path);
        files.push({
          name,
          size: stat.size,
          downloadUrl: `/api/downloads/${encodeURIComponent(name)}`,
          modifiedAt: stat.mtime?.toISOString() ?? new Date().toISOString(),
        });
      }
    } catch {
      // directory may not exist yet
    }
  }

  // Sort newest first
  files.sort((a, b) => new Date(b.modifiedAt).getTime() - new Date(a.modifiedAt).getTime());

  ctx.response.body = { files };
});

router.delete("/api/outputs", async (ctx: Context) => {
  let deleted = 0;

  for (const dir of [config.vaultOutputDir, config.outputDir]) {
    try {
      for await (const entry of walk(dir, { includeDirs: false, maxDepth: 1 })) {
        try {
          await Deno.remove(entry.path);
          deleted += 1;
        } catch {
          // skip files that can't be deleted
        }
      }
    } catch {
      // directory may not exist
    }
  }

  ctx.response.body = { deleted, message: `${deleted} output file(s) cleared.` };
});

router.post("/api/convert", async (ctx: Context) => {
  if (shuttingDown) {
    ctx.response.status = 503;
    ctx.response.body = createError("SHUTTING_DOWN", "Service is shutting down", {}, true);
    return;
  }

  if (!ctx.request.hasBody) {
    ctx.response.status = 400;
    ctx.response.body = createError("INVALID_REQUEST", "Missing request body", {}, false);
    return;
  }

  const formData = await ctx.request.body.formData();

  const targetValue = (formData.get("target") as string) ?? "";
  const targetMapStr = formData.get("targetMap") as string | null;
  const targetMap: Record<string, string> = targetMapStr ? JSON.parse(targetMapStr) : {};

  const sourceTypeValue = (formData.get("sourceType") as string) ?? "auto";
  const yamlFrontmatterStr = formData.get("yamlFrontmatter") as string | null;
  const yamlFrontmatterValue = parseBoolean(yamlFrontmatterStr);

  const files: File[] = [];
  for (const [key, value] of formData.entries()) {
    if (key === "files" && value instanceof File) {
      files.push(value);
    }
  }

  if (!isValidSourceType(sourceTypeValue)) {
    ctx.response.status = 400;
    ctx.response.body = createError("INVALID_REQUEST", "Unsupported source type value", {
      sourceType: sourceTypeValue,
    }, false);
    return;
  }

  if (yamlFrontmatterValue === null && yamlFrontmatterStr) {
    ctx.response.status = 400;
    ctx.response.body = createError("INVALID_REQUEST", "Malformed boolean flag", {
      yamlFrontmatter: yamlFrontmatterStr,
    }, false);
    return;
  }

  if (files.length === 0) {
    ctx.response.status = 400;
    ctx.response.body = createError("INVALID_REQUEST", "At least one file is required", {}, false);
    return;
  }

  if (files.length > config.maxFilesPerRequest) {
    ctx.response.status = 400;
    ctx.response.body = createError("TOO_MANY_FILES", "Too many files in a single request", {
      maxFilesPerRequest: config.maxFilesPerRequest,
    }, false);
    return;
  }

  const batchId = `${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;
  const results: ConversionResult[] = [];

  for (const file of files) {
    const originalName = file.name || "upload.pdf";
    const extension = extname(originalName).toLowerCase();
    const fileTarget = targetMap[originalName] || targetValue;

    if (!isValidTarget(fileTarget)) {
      results.push({
        inputName: originalName,
        storedUploadName: originalName,
        target: fileTarget,
        sourceType: normalizeSourceType(sourceTypeValue),
        status: "failed",
        outputFileName: null,
        outputPath: null,
        downloadUrl: null,
        durationMs: 0,
        error: createError(
          "INVALID_TARGET",
          `Invalid or unsupported target format: ${fileTarget}`,
          { target: fileTarget },
          false,
        ),
      });
      continue;
    }

    const isXlsx = [".xlsx", ".xlsm"].includes(extension);

    if (![".pdf", ".md", ".markdown", ".xlsx", ".xlsm"].includes(extension)) {
      results.push({
        inputName: originalName,
        storedUploadName: originalName,
        target: fileTarget as ConversionTarget,
        sourceType: normalizeSourceType(sourceTypeValue),
        status: "failed",
        outputFileName: null,
        outputPath: null,
        downloadUrl: null,
        durationMs: 0,
        error: createError(
          "UNSUPPORTED_FILE_TYPE",
          "Supported types: PDF, Markdown, XLSX",
          { fileName: originalName },
          false,
        ),
      });
      continue;
    }

    const storedName = `${crypto.randomUUID()}${extension}`;
    const conversionId = `${batchId}-${crypto.randomUUID().slice(0, 8)}`;

    try {
      const inputPath = await persistUploadedFile(file, storedName);
      const yamlFrontmatter = fileTarget === "vault_md"
        ? (yamlFrontmatterValue ?? true)
        : false;

      const outputDirectory = fileTarget === "vault_md" || fileTarget === "vault_json"
        ? config.vaultOutputDir
        : config.outputDir;

      const outputExtension = fileTarget === "vault_md"
        ? ".md"
        : fileTarget === "vault_json"
        ? ".json"
        : fileTarget === "html"
        ? ".html"
        : fileTarget === "docx"
        ? ".docx"
        : ".pdf";

      const requestedOutputName = safeOutputName(originalName, outputExtension);
      const outputPath = await uniqueOutputPath(outputDirectory, requestedOutputName);

      let durationMs = 0;
      let effectiveSourceType: EffectiveSourceType = normalizeSourceType(sourceTypeValue);

      if (isXlsx) {
        const xlsxTarget = fileTarget === "vault_json" ? "vault_json" : "vault_md";
        const xlsxOutputExt = xlsxTarget === "vault_json" ? ".json" : ".md";
        const xlsxOutputDir = config.vaultOutputDir;
        const xlsxOutputName = safeOutputName(originalName, xlsxOutputExt);
        const xlsxOutputPath = await uniqueOutputPath(xlsxOutputDir, xlsxOutputName);

        const xlsxResult = await runXlsxConversion(
          inputPath,
          xlsxOutputPath,
          xlsxTarget,
          yamlFrontmatter,
          conversionId,
        );
        durationMs = xlsxResult.durationMs;
        effectiveSourceType = "generic";

        const xlsxOutputFileName = basename(xlsxOutputPath);
        results.push({
          inputName: originalName,
          storedUploadName: storedName,
          target: xlsxTarget,
          sourceType: effectiveSourceType,
          status: "completed",
          outputFileName: xlsxOutputFileName,
          outputPath: xlsxOutputPath,
          downloadUrl: buildDownloadUrl(xlsxOutputFileName),
          durationMs,
          error: null,
          conversionId,
        });
        
        // Send completion event via SSE
        sendSSEComplete(conversionId, {
          outputFileName: xlsxOutputFileName,
          downloadUrl: buildDownloadUrl(xlsxOutputFileName),
        });
        continue;
      } else if (fileTarget === "vault_md") {
        const result = await runPythonConversion(
          inputPath,
          outputPath,
          sourceTypeValue,
          yamlFrontmatter,
          conversionId,
        );
        durationMs = result.durationMs;
        effectiveSourceType = result.sourceType;
      } else {
        durationMs = await runPandocConversion(inputPath, outputPath);
      }

      const outputFileName = basename(outputPath);

      results.push({
        inputName: originalName,
        storedUploadName: storedName,
        target: fileTarget,
        sourceType: effectiveSourceType,
        status: "completed",
        outputFileName,
        outputPath,
        downloadUrl: buildDownloadUrl(outputFileName),
        durationMs,
        error: null,
        conversionId,
      });
      
      // Send completion event via SSE
      sendSSEComplete(conversionId, {
        outputFileName,
        downloadUrl: buildDownloadUrl(outputFileName),
      });
    } catch (error) {
      const knownError = typeof error === "object" && error !== null && "code" in error
        ? error as ConversionError
        : createError(
          "CONVERSION_FAILED",
          error instanceof Error ? error.message : "Conversion failed",
          {},
          true,
        );

      results.push({
        inputName: originalName,
        storedUploadName: storedName,
        target: fileTarget,
        sourceType: normalizeSourceType(sourceTypeValue),
        status: "failed",
        outputFileName: null,
        outputPath: null,
        downloadUrl: null,
        durationMs: 0,
        error: knownError,
        conversionId,
      });
      
      // Send error event via SSE
      sendSSEError(conversionId, knownError);
    }
  }

  ctx.response.status = 200;
  ctx.response.body = {
    batchId,
    status: results.every((item) => item.status === "completed")
      ? "completed"
      : "completed_with_possible_failures",
    results,
    errors: results.filter((item) => item.error).map((item) => item.error),
  };
});

router.get("/", async (ctx: Context) => {
  await send(ctx, "index.html", {
    root: join(Deno.cwd(), "static"),
  });
});

router.get("/app.js", async (ctx: Context) => {
  await send(ctx, "app.js", {
    root: join(Deno.cwd(), "static"),
  });
});

app.use(async (ctx: Context, next: () => Promise<unknown>) => {
  try {
    await next();
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = createError(
      "INTERNAL_ERROR",
      error instanceof Error ? error.message : "Unexpected server error",
      {},
      false,
    );
  }
});

app.use(router.routes());
app.use(router.allowedMethods());

const cleanupTimer = setInterval(() => {
  cleanupUploads().catch(() => undefined);
}, config.uploadRetentionMinutes * 60 * 1000);

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  Deno.addSignalListener(signal, () => {
    shuttingDown = true;
    clearInterval(cleanupTimer);
    for (const proc of activeProcesses) {
      try {
        proc.kill("SIGTERM");
      } catch {
        // ignore shutdown errors
      }
    }
  });
}

await ensureDirectories();
await cleanupUploads();

console.log(`MarkDone listening on http://${config.bindHost}:${config.port}`);
await app.listen({ hostname: config.bindHost, port: config.port });

// Made with Bob
