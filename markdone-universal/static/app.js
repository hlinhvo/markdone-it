let queue = [];
let target = "vault_md";
let sourceType = "auto";
let yamlFrontmatter = true;
let highFidelity = true;
let feedback = "Ready.";
let health = { status: "Checking…", concurrency: "-" };

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function updateDOM() {
  document.getElementById("metric-files").textContent = String(queue.length);
  document.getElementById("metric-target").textContent = target;
  document.getElementById("metric-health").textContent = health.status;
  document.getElementById("metric-concurrency").textContent = health.concurrency;
  document.getElementById("feedback").textContent = feedback;
  renderQueueTable();
}

function renderQueueTable() {
  const tbody = document.getElementById("queue-body");
  if (queue.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="small">No files staged yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = "";
  queue.forEach(item => {
    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.textContent = item.name;
    tr.appendChild(nameTd);

    const sizeTd = document.createElement("td");
    sizeTd.textContent = formatBytes(item.size);
    tr.appendChild(sizeTd);

    const targetTd = document.createElement("td");
    if (item.status === "queued") {
      const select = document.createElement("select");
      const isExcelFile = item.name.toLowerCase().endsWith(".xlsx") || item.name.toLowerCase().endsWith(".xlsm");
      select.innerHTML = `
        <option value="vault_md" ${item.targetFormat === "vault_md" ? "selected" : ""}>Vault MD</option>
        <option value="html" ${item.targetFormat === "html" ? "selected" : ""}>HTML</option>
        <option value="docx" ${item.targetFormat === "docx" ? "selected" : ""}>DOCX</option>
        <option value="pdf" ${item.targetFormat === "pdf" ? "selected" : ""}>PDF</option>
        ${isExcelFile ? `<option value="vault_json" ${item.targetFormat === "vault_json" ? "selected" : ""}>JSON (structured)</option>` : ""}
      `;
      select.style.padding = "4px 8px";
      select.style.fontSize = "12px";
      select.onchange = (e) => {
        item.targetFormat = e.target.value;
      };
      targetTd.appendChild(select);
    } else {
      targetTd.textContent = item.targetFormat;
    }
    tr.appendChild(targetTd);

    const typeTd = document.createElement("td");
    typeTd.textContent = item.sourceType;
    tr.appendChild(typeTd);

    const statusTd = document.createElement("td");
    statusTd.innerHTML = `<span class="status-pill status-${item.status}">${item.status}</span>`;
    if (item.error) {
      const errDiv = document.createElement("div");
      errDiv.className = "small";
      errDiv.textContent = item.error;
      statusTd.appendChild(errDiv);
    }
    tr.appendChild(statusTd);

    const outTd = document.createElement("td");
    if (item.outputName && item.downloadUrl) {
      const link = document.createElement("a");
      link.href = item.downloadUrl;
      link.download = item.outputName;
      link.className = "output-link";
      link.textContent = item.outputName;
      outTd.appendChild(link);
    } else {
      outTd.innerHTML = item.outputName ? `<span class="small">${item.outputName}</span>` : `<span class="small">-</span>`;
    }
    tr.appendChild(outTd);

    const actionTd = document.createElement("td");
    if (item.status === "completed" && item.downloadUrl) {
      const dlBtn = document.createElement("a");
      dlBtn.href = item.downloadUrl;
      dlBtn.download = item.outputName;
      dlBtn.className = "btn-download";
      dlBtn.textContent = "⬇ Download";
      dlBtn.setAttribute("role", "button");
      actionTd.appendChild(dlBtn);
    }
    const btn = document.createElement("button");
    btn.className = "remove-btn";
    btn.textContent = "Remove";
    btn.onclick = () => removeFile(item.id);
    actionTd.appendChild(btn);
    tr.appendChild(actionTd);

    tbody.appendChild(tr);
  });
}

function createQueueItem(file) {
  return {
    id: crypto.randomUUID(),
    file,
    name: file.name,
    size: file.size,
    targetFormat: document.getElementById("target-select").value,
    sourceType: sourceType,
    status: "queued",
    outputPath: "",
    outputName: "",
    downloadUrl: "",
    error: "",
  };
}

function addFiles(fileList) {
  const incoming = Array.from(fileList)
    .filter((file) => {
      const name = file.name.toLowerCase();
      return file.type === "application/pdf" ||
             file.type === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
             file.type === "application/vnd.ms-excel.sheet.macroEnabled.12" ||
             name.endsWith(".pdf") ||
             name.endsWith(".md") ||
             name.endsWith(".markdown") ||
             name.endsWith(".xlsx") ||
             name.endsWith(".xlsm");
    })
    .map(createQueueItem);

  if (incoming.length === 0) {
    feedback = "Only PDF, Markdown, and Excel files (.xlsx, .xlsm) can be added to the staging queue.";
    updateDOM();
    return;
  }

  const existingNames = new Set(queue.map((item) => item.name));
  const deduped = incoming.filter((item) => !existingNames.has(item.name));
  queue = [...queue, ...deduped];
  feedback = `${deduped.length} file(s) added to staging.`;
  updateDOM();
}

window.removeFile = function(id) {
  queue = queue.filter((item) => item.id !== id);
  updateDOM();
};

function clearQueue() {
  queue = [];
  feedback = "Staging queue cleared.";
  updateDOM();
}

async function refreshHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    health = {
      status: data.status,
      concurrency: `${data.concurrency.active}/${data.concurrency.limit}`,
    };
  } catch {
    health = {
      status: "Unavailable",
      concurrency: "-",
    };
  }
  updateDOM();
}

async function convertAll() {
  if (queue.length === 0) {
    feedback = "Add at least one PDF before converting.";
    updateDOM();
    return;
  }

  queue = queue.map((item) => ({
    ...item,
    status: "uploading",
    error: "",
  }));
  feedback = "Uploading staged files…";
  updateDOM();

  const formData = new FormData();
  formData.append("target", target);
  formData.append("sourceType", sourceType);
  
  // We send the global toggle value to the backend, but the backend will use it
  // whenever a file is targeted to vault_md.
  formData.append("yamlFrontmatter", String(yamlFrontmatter));

  const targetMap = {};
  for (const item of queue) {
    formData.append("files", item.file, item.name);
    targetMap[item.name] = item.targetFormat;
  }
  formData.append("targetMap", JSON.stringify(targetMap));

  try {
    queue = queue.map((item) => ({ ...item, status: "converting" }));
    updateDOM();

    const response = await fetch("/api/convert", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.message ?? "Conversion request failed");
    }

    const resultMap = new Map(data.results.map((result) => [result.inputName, result]));
    queue = queue.map((item) => {
      const result = resultMap.get(item.name);
      if (!result) {
        return {
          ...item,
          status: "failed",
          error: "No result returned for file.",
        };
      }

      return {
        ...item,
        sourceType: result.sourceType,
        status: result.status,
        outputPath: result.outputPath ?? "",
        outputName: result.outputFileName ?? "",
        downloadUrl: result.downloadUrl ?? "",
        error: result.error?.message ?? "",
      };
    });

    const failures = queue.filter((item) => item.status === "failed").length;
    feedback = failures > 0
      ? `Conversion finished with ${failures} failure(s).`
      : "Conversion completed successfully.";
  } catch (error) {
    queue = queue.map((item) => ({
      ...item,
      status: "failed",
      error: error instanceof Error ? error.message : "Conversion failed",
    }));
    feedback = "Conversion failed.";
  } finally {
    refreshHealth();
    updateDOM();
  }
}

function wireDom() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const targetSelect = document.getElementById("target-select");
  const sourceTypeSelect = document.getElementById("source-type-select");
  const frontmatterToggle = document.getElementById("frontmatter-toggle");
  const highFidelityToggle = document.getElementById("high-fidelity-toggle");
  const convertButton = document.getElementById("convert-button");
  const clearButton = document.getElementById("clear-button");

  fileInput.addEventListener("change", (event) => {
    addFiles(event.target.files ?? []);
    fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    addFiles(event.dataTransfer?.files ?? []);
  });

  targetSelect.addEventListener("change", (event) => {
    target = event.target.value;
    const isVault = target === "vault_md";
    highFidelityToggle.disabled = !isVault;
    frontmatterToggle.disabled = !isVault;
    if (!isVault) {
      highFidelity = false;
      yamlFrontmatter = false;
      highFidelityToggle.checked = false;
      frontmatterToggle.checked = false;
    } else {
      highFidelity = true;
      yamlFrontmatter = true;
      highFidelityToggle.checked = true;
      frontmatterToggle.checked = true;
    }
    updateDOM();
  });

  sourceTypeSelect.addEventListener("change", (event) => {
    sourceType = event.target.value;
    queue = queue.map((item) => ({
      ...item,
      sourceType: item.status === "completed" ? item.sourceType : sourceType,
    }));
    updateDOM();
  });

  frontmatterToggle.addEventListener("change", (event) => {
    yamlFrontmatter = event.target.checked;
  });

  highFidelityToggle.addEventListener("change", (event) => {
    highFidelity = event.target.checked;
  });

  convertButton.addEventListener("click", async () => {
    await convertAll();
    loadOutputFiles();
  });
  clearButton.addEventListener("click", clearQueue);

  const clearHistoryButton = document.getElementById("clear-history-button");
  clearHistoryButton.addEventListener("click", clearHistory);

  refreshHealth();
  setInterval(refreshHealth, 10000);
  loadOutputFiles();
}

async function clearHistory() {
  if (!confirm("Delete all converted output files?")) return;

  try {
    const response = await fetch("/api/outputs", { method: "DELETE" });
    const data = await response.json();
    feedback = data.message || "History cleared.";
  } catch {
    feedback = "Failed to clear history.";
  }
  updateDOM();
  loadOutputFiles();
}

async function loadOutputFiles() {
  const tbody = document.getElementById("output-body");
  if (!tbody) return;

  try {
    const response = await fetch("/api/outputs");
    const data = await response.json();
    const files = data.files || [];

    if (files.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" class="small">No converted files yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    files.forEach(file => {
      const tr = document.createElement("tr");

      const nameTd = document.createElement("td");
      const link = document.createElement("a");
      link.href = file.downloadUrl;
      link.download = file.name;
      link.className = "output-link";
      link.textContent = file.name;
      nameTd.appendChild(link);
      tr.appendChild(nameTd);

      const sizeTd = document.createElement("td");
      sizeTd.textContent = formatBytes(file.size);
      tr.appendChild(sizeTd);

      const dateTd = document.createElement("td");
      dateTd.className = "small";
      dateTd.textContent = new Date(file.modifiedAt).toLocaleString();
      tr.appendChild(dateTd);

      const actionTd = document.createElement("td");
      const dlBtn = document.createElement("a");
      dlBtn.href = file.downloadUrl;
      dlBtn.download = file.name;
      dlBtn.className = "btn-download";
      dlBtn.textContent = "\u2b07 Download";
      dlBtn.setAttribute("role", "button");
      actionTd.appendChild(dlBtn);
      tr.appendChild(actionTd);

      tbody.appendChild(tr);
    });
  } catch {
    tbody.innerHTML = `<tr><td colspan="4" class="small">Could not load output files.</td></tr>`;
  }
}

document.addEventListener("DOMContentLoaded", wireDom);

// Made with Bob
