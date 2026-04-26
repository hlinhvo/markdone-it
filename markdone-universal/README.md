# MarkDone Universal

MarkDone Universal is a local-first document conversion tool designed for single-user production use on a MacBook Pro 16. It combines:

- a Deno 2.x orchestration API
- a Python high-fidelity PDF-to-Markdown sidecar
- a zero-build frontend using Preact, HTM, and Pico CSS
- Podman deployment with a local vault directory mount

## Features

- **High-fidelity PDF to Markdown conversion** with intelligent source detection
- **Real-time progress tracking** via Server-Sent Events (SSE) for large file conversions
- **Bulk download as ZIP** - download multiple converted files in a single archive
- **Smart download behavior** - single files download directly, 2+ files download as ZIP
- **Batch staging queue** with drag-and-drop support
- **YAML frontmatter toggle** for Markdown output
- **Excel/XLSX support** with structured JSON or Markdown table output
- **Local-only deployment** and processing (no data leaves your machine)
- **Podman Kube Play deployment** with resource limits
- **Secure permissions model** - minimal Deno permissions (no `--allow-all`)
- **Upload cleanup** and graceful shutdown behavior
- **Direct downloads** for all conversion targets
- **User-friendly UI** with clear terminology and responsive table layouts

## Project Layout

```text
markdone-universal/
├── Containerfile
├── deno.json
├── deploy.sh
├── podman-kube.yaml
├── README.md
├── server.ts
├── services/
│   └── high_fidelity_pdf.py
├── static/
│   ├── app.js
│   └── index.html
├── tests/
├── uploads/
└── outputs/
```

## Prerequisites

- macOS on your MacBook Pro 16
- Podman Desktop 1.26+
- Deno 2.x
- A local output directory at `../outputs` (to be created by `setup.sh`)

## Setup

```bash
cd ./markdone-universal
chmod +x ./setup.sh ./deploy.sh
./setup.sh
```

The setup script checks:

- Podman availability
- Deno availability
- Output vault directory existence

## Run in Development

```bash
cd ./markdone-universal
deno task dev
```

The app starts on:

- UI: `http://127.0.0.1:7482`
- Health: `http://127.0.0.1:7482/health`

## Deploy with Podman

```bash
cd ./markdone-universal
./deploy.sh
```

This will:

- build the image `localhost/markdone-universal:latest`
- replace any existing `markdone-universal` pod
- run [`podman kube play`](deploy.sh) with [`podman-kube.yaml`](podman-kube.yaml)

## Resource Profiles

### Sleep Mode
Configured via resource requests in [`podman-kube.yaml`](podman-kube.yaml):

- CPU: `50m`
- Memory: `128Mi`

### Burst Mode
Configured via resource limits in [`podman-kube.yaml`](podman-kube.yaml):

- CPU: `4`
- Memory: `2Gi`

### Concurrency
Default conversion concurrency is `4`, tuned for a single-user local workflow. It can be increased to `6` after validating stability on your machine.

## API

### [`GET /health`](server.ts)
Returns:

- service health
- dependency availability for `pandoc` and `python3`
- uptime
- active versus configured concurrency

### [`POST /api/convert`](server.ts)
`multipart/form-data` fields:

- `target`: `vault_md|vault_json|html|docx|pdf`
- `sourceType`: `auto|ppt|word|generic`
- `yamlFrontmatter`: `true|false`
- `files`: one or more PDF, Markdown, or Excel files
- `targetMap`: (optional) JSON object mapping filenames to specific targets

Returns conversion results with `conversionId` for each file.

### [`GET /api/convert/progress/:conversionId`](server.ts)
**New in v1.1**: Server-Sent Events endpoint for real-time progress updates.

Events:
- `connected`: Initial connection established
- `progress`: Progress update with `{progress, current, total, message}`
- `complete`: Conversion completed with `{outputFileName, downloadUrl}`
- `error`: Conversion failed with error details

### [`GET /api/downloads/:fileName`](server.ts)
Download converted files.

### [`POST /api/download-queue-zip`](server.ts)
**New in v2.2**: Download multiple files from the processing queue as a ZIP archive.

Request body:
```json
{
  "files": [
    {"path": "relative/path/to/file1.md"},
    {"path": "relative/path/to/file2.md"}
  ]
}
```

Returns a ZIP file with timestamped filename (e.g., `markdone-queue-2026-04-26-15-30-45.zip`).

### [`GET /api/download-history-zip`](server.ts)
**New in v2.2**: Download all completed files from the history as a ZIP archive.

Returns a ZIP file with timestamped filename (e.g., `markdone-history-2026-04-26-15-30-45.zip`).

### [`GET /api/outputs`](server.ts)
List all converted output files with metadata.

### [`DELETE /api/outputs`](server.ts)
Clear all output files from the vault.

## Frontend Workflow

1. Add one or more PDFs using drag-and-drop or the file picker.
2. Review the staging queue.
3. Remove any files you do not want.
4. Select target and source type.
5. Use frontmatter and high-fidelity options for Markdown output.
6. Click **Convert All**.
7. Download files individually or use **Download All** to get multiple files as a ZIP archive.
8. View completed files in the **Completed Files** section with download history.

## Output Behavior

- Markdown files are written to the mounted vault path at `/app/outputs/vault`
- Other targets are written under `/app/outputs`
- All outputs may be downloaded via `/api/downloads/:fileName`

## Logging and Health

The backend logs:

- startup
- conversion success and failure
- dependency availability
- cleanup lifecycle events

Health response includes active concurrency and dependency status.

## Cleanup Behavior

Uploads in [`uploads/`](uploads/) older than 10 minutes are purged automatically.

## Graceful Shutdown

On `SIGINT` or `SIGTERM`, the server:

- stops accepting new work
- clears the cleanup timer
- terminates active child conversion processes

## Security

### Deno Permissions
MarkDone Universal follows the **principle of least privilege**:

```bash
--allow-net          # HTTP server only
--allow-read         # Read uploads, services, static files
--allow-write        # Write to uploads and outputs directories
--allow-env          # Read configuration from environment variables
--allow-run=python3,pandoc  # Execute only specific commands
```

**No `--allow-all`** - the application requests only the minimum permissions required.

### Data Privacy
- All processing happens locally on your machine
- No data is sent to external services
- Files are automatically cleaned up after 10 minutes
- Vault directory is mounted read-write for output only

## Progress Tracking

For large files (50+ pages), MarkDone provides real-time progress updates:

1. **Backend**: Python scripts emit progress events to stderr
2. **Server**: Deno captures events and relays via SSE
3. **Frontend**: Progress bar updates in real-time showing:
   - Percentage complete (0-100%)
   - Current page / Total pages
   - Visual progress bar with gradient

Progress tracking works for:
- PDF conversions (per-page progress)
- Excel conversions (per-sheet progress)

## Known Limitations

- Version 1 is single-user and local-only
- Public exposure is unsupported
- Pandoc support for some PDF conversion routes may be limited by upstream behavior
- The editor may require Deno support enabled for best TypeScript diagnostics
- SSE connections timeout after 5 minutes of inactivity

## Troubleshooting

### Podman pod does not start
```bash
podman pod ps
podman logs -f markdone-api
```

### Health endpoint is degraded
Check whether `pandoc` and `python3` are available inside the container or local environment.

### Output is not appearing in local folder
Verify the host path in your deployment manifest matches your actual output directory.

### Deno types show unresolved in VS Code
Open the [`markdone-universal/`](.) folder directly or ensure the Deno extension is enabled for the workspace.

## Implementation Baseline

This project was implemented from [`markdone-production-spec.md`](../docs/markdone-production-spec.md).