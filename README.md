# MarkDone-IT v2

A local-first, production-ready document conversion tool that converts PDFs, Markdown, and Excel workbooks into AI-ready formats — optimised for use with Claude Projects, NotebookLM, and direct Anthropic API RAG workflows.

Built with a Deno 2.x orchestration API, a Python conversion sidecar, a zero-build Preact frontend, and Podman deployment for MacBook Pro 16.

---

## Why MarkDone-IT

Large PDF and XLSX files consume significant tokens when uploaded directly to AI tools. MarkDone-IT converts them to lightweight Markdown or structured JSON first — reducing token consumption by 60–80% and making document-heavy workflows substantially faster and cheaper.

---

## Features

### v2.2 (Current)
- **Bulk download as ZIP** — download multiple converted files in a single archive
- **Smart download behavior** — single files download directly, 2+ files download as ZIP with timestamps
- **User-friendly UI** — clear terminology ("Completed Files" instead of technical jargon)
- **Responsive table layouts** — long filenames handled gracefully without breaking layout

### v2.1 (Retained)
- XLSX and XLSM to Markdown table conversion (`vault_md`)
- XLSX and XLSM to structured JSON conversion (`vault_json`) — most token-efficient format for RAG
- Auto-detection of compliance matrix sheets (RFP/RFI workflows)
- YAML frontmatter with `lang: en` tag on all Markdown outputs
- **Real-time progress tracking** via Server-Sent Events for large file conversions

### v1 (Retained)
- High-fidelity PDF to Markdown conversion (printed PDFs with selectable text)
- PDF, Markdown to HTML, DOCX, and PDF output via Pandoc
- Batch staging queue with drag-and-drop
- YAML frontmatter toggle for Markdown output
- Source type detection: `auto`, `ppt`, `word`, `generic`
- Local-only deployment and processing
- Upload cleanup and graceful shutdown behaviour

---

## Project Layout

```
markdone-it/
├── Containerfile               # Multi-stage container image (Deno + Python 3.11)
├── deno.json                   # Deno task configuration
├── deploy.sh                   # Podman build and deploy script
├── setup.sh                    # Prerequisites check and directory setup
├── podman-kube.yaml            # Podman Kube Play manifest (sleep/burst resource profiles)
├── server.ts                   # Deno 2.x orchestration API (Oak framework)
├── tsconfig.json               # TypeScript configuration
├── services/
│   ├── high_fidelity_pdf.py   # PDF → Markdown sidecar (PyMuPDF)
│   ├── xlsx_converter.py      # XLSX/XLSM → Markdown / JSON sidecar (pandas + openpyxl)
│   └── legacy/                # Legacy extraction and formatting modules
├── static/
│   ├── index.html             # Single-page UI shell
│   └── app.js                 # Preact + HTM frontend (zero-build)
└── tests/                      # Test suite
```

---

## Prerequisites

- macOS (MacBook Pro 16 recommended)
- Podman Desktop 1.26+
- Deno 2.x

---

## Setup

```bash
chmod +x ./setup.sh ./deploy.sh
./setup.sh
```

The setup script verifies Podman availability, Deno availability, and creates the local output vault directory.

---

## Development

```bash
deno task dev
```

- UI: `http://127.0.0.1:7482`
- Health: `http://127.0.0.1:7482/health`

---

## Production Deployment

```bash
./deploy.sh
```

This builds `localhost/markdone-universal:latest`, tears down any existing pod, and runs `podman kube play` with `podman-kube.yaml`.

- UI and API: `http://localhost:7482`
- Health: `http://localhost:7482/health`

---

## Resource Profiles

Configured in `podman-kube.yaml`:

| Mode | CPU | Memory |
|---|---|---|
| Sleep (requests) | `50m` | `128Mi` |
| Burst (limits) | `4` | `2Gi` |

Default conversion concurrency: `4` (tunable via `MAX_CONCURRENT_CONVERSIONS` env var).

---

## API

### `GET /health`

Returns service status, dependency availability (`pandoc`, `python3`), uptime, supported inputs and targets, and active concurrency.

```json
{
  "status": "ok",
  "dependencies": { "pandoc": true, "python3": true },
  "supportedInputs": ["pdf", "md", "xlsx", "xlsm"],
  "supportedTargets": ["vault_md", "vault_json", "docx", "html", "pdf"]
}
```

### `POST /api/convert`

`multipart/form-data` fields:

| Field | Values | Notes |
|---|---|---|
| `files` | one or more files | PDF, Markdown, XLSX, XLSM |
| `target` | `vault_md` \| `vault_json` \| `html` \| `docx` \| `pdf` | `vault_json` applies to XLSX/XLSM only |
| `sourceType` | `auto` \| `ppt` \| `word` \| `generic` | PDF only, ignored for XLSX |
| `yamlFrontmatter` | `true` \| `false` | Markdown output only |

#### Example — XLSX via curl (bypassing the UI)

```bash
curl -X POST http://localhost:7482/api/convert \
  -F "files=@compliance_matrix.xlsx" \
  -F "target=vault_md" \
  -F "yamlFrontmatter=true"
```

#### Example — XLSX to JSON for direct RAG use

```bash
curl -X POST http://localhost:7482/api/convert \
  -F "files=@rfp_requirements.xlsx" \
  -F "target=vault_json"
```

### `GET /api/downloads/:fileName`

Download a converted output file by name.

### `POST /api/download-queue-zip`

**New in v2.2**: Download multiple files from the processing queue as a ZIP archive with timestamped filename.

### `GET /api/download-history-zip`

**New in v2.2**: Download all completed files from history as a ZIP archive with timestamped filename.

### `GET /api/outputs`

List all output files with download URLs, sizes, and modification timestamps.

### `DELETE /api/outputs`

Clear all output files.

---

## Frontend Workflow

1. Add files using drag-and-drop or the file picker (PDF, MD, XLSX, XLSM supported).
2. Review the staging queue.
3. Remove any files you do not want to convert.
4. Select target format and source type.
5. Toggle YAML frontmatter for Markdown output.
6. Click **Convert All**.
7. Download files individually or use **Download All** to get multiple files as a ZIP archive.
8. View completed files in the **Completed Files** section with download history.

---

## Output Behaviour

| Target | Output path | Notes |
|---|---|---|
| `vault_md` | `/app/outputs/vault/` | Markdown with optional YAML frontmatter |
| `vault_json` | `/app/outputs/vault/` | Structured JSON, XLSX/XLSM only |
| `html` | `/app/outputs/` | Via Pandoc |
| `docx` | `/app/outputs/` | Via Pandoc |
| `pdf` | `/app/outputs/` | Via Pandoc + WeasyPrint |

The vault directory is bind-mounted from the host — files written there persist across pod restarts.

---

## XLSX Conversion Detail

`xlsx_converter.py` follows the same CLI contract as `high_fidelity_pdf.py`:

- Reads all sheets in the workbook
- Skips chart-only, empty, or protected sheets gracefully
- Auto-detects compliance matrix sheets (column headers matching keywords: `requirement`, `compliance`, `response`, `status`, `vendor`, `criteria`, etc.)
- Compliance sheets are flagged in YAML frontmatter and JSON output for downstream filtering
- Caps rows at 2,000 per sheet and cells at 500 characters to prevent runaway output
- `vault_md`: one `## Sheet Name` section per sheet with a full Markdown table
- `vault_json`: structured JSON with column list, row count, sheet type, and all rows as records

---

## Architecture

| Layer | Technology |
|---|---|
| Orchestration API | Deno 2.x + Oak framework |
| PDF conversion | Python 3.11 + PyMuPDF (sidecar) |
| XLSX conversion | Python 3.11 + pandas + openpyxl (sidecar) |
| Format conversion | Pandoc + WeasyPrint |
| Frontend | Preact + HTM (zero-build, no bundler) |
| Styling | Pico CSS |
| Deployment | Podman Kube Play |
| Container base | `python:3.11-slim` + Deno binary copy |

---

## Logging and Health

The backend logs startup, conversion success and failure, dependency availability, and cleanup lifecycle events. All Python sidecar output goes to stderr — only the JSON result payload reaches stdout for Deno to parse.

---

## Cleanup Behaviour

Uploads older than 10 minutes are purged automatically on a rolling timer.

---

## Graceful Shutdown

On `SIGINT` or `SIGTERM`, the server stops accepting new work, clears the cleanup timer, and terminates all active child conversion processes.

---

## Known Limitations

- Single-user, local-only — not designed for public exposure
- PDF conversion requires printed PDFs with selectable text (scanned PDFs are not supported in v2)
- XLSX conversion is English-language only in v2
- Pandoc PDF output requires WeasyPrint; LaTeX is not used

---

## Roadmap

| Version | Planned |
|---|---|
| v2 ✅ | XLSX/XLSM support, `vault_json` target, compliance matrix detection |
| v3 | Scanned PDF via Claude Vision API (English first), Vietnamese language support |

---

## Troubleshooting

**Pod does not start**
```bash
podman pod ps
podman logs -f markdone-api
```

**Health endpoint is degraded**
Check that `pandoc` and `python3` are available inside the container.

**XLSX file not selectable in UI**
Ensure the file picker `accept` attribute includes `.xlsx,.xlsm` and that both MIME types are listed in the frontend validation.

**Output not appearing in local folder**
Verify the host path in `podman-kube.yaml` matches your actual output directory.

**Deno types unresolved in VS Code**
Open the repo root directly and ensure the Deno VS Code extension is enabled for the workspace.

---

## License

Internal use only.
