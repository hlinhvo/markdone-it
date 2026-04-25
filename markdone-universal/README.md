# MarkDone Universal

MarkDone Universal is a local-first document conversion tool designed for single-user production use on a MacBook Pro 16. It combines:

- a Deno 2.x orchestration API
- a Python high-fidelity PDF-to-Markdown sidecar
- a zero-build frontend using Preact, HTM, and Pico CSS
- Podman deployment with a local vault directory mount

## Features

- High-fidelity PDF to Markdown conversion
- Batch staging queue with drag-and-drop
- YAML frontmatter toggle for Markdown output
- Local-only deployment and processing
- Podman Kube Play deployment
- Upload cleanup and graceful shutdown behavior
- Optional direct downloads for all targets

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

- `target`: `vault_md|html|docx|pdf`
- `sourceType`: `auto|ppt|word|generic`
- `yamlFrontmatter`: `true|false`
- `files`: one or more PDF files

## Frontend Workflow

1. Add one or more PDFs using drag-and-drop or the file picker.
2. Review the staging queue.
3. Remove any files you do not want.
4. Select target and source type.
5. Use frontmatter and high-fidelity options for Markdown output.
6. Click **Convert All**.

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

## Known Limitations

- Version 1 is single-user and local-only
- Public exposure is unsupported
- Pandoc support for some PDF conversion routes may be limited by upstream behavior
- The editor may require Deno support enabled for best TypeScript diagnostics

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