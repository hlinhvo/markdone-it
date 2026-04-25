# MarkDone Session Memory

## Current objective

Implement and validate [`markdone-universal/`](markdone-universal/) from [`markdone-production-spec.md`](markdone-production-spec.md) for **single-user local production** on a MacBook Pro 16, using Podman CLI/Desktop for containerized validation.

## Completed work

### Specification and planning
- Reviewed the original draft in [`implementation-plan-markdone`](implementation-plan-markdone).
- Determined the original draft was **not production-ready**.
- Created a formal production-ready specification in [`markdone-production-spec.md`](markdone-production-spec.md).
- Revised the spec for **single-user local production** instead of multi-user/team-scale production.
- User approved the spec as-is and requested implementation.

### Implementation location
- Chosen target project: [`markdone-universal/`](markdone-universal/)
- Reuse selected logic from [`pdf-to-obsidian-md-v2/src/`](pdf-to-obsidian-md-v2/src/)

### Files created in [`markdone-universal/`](markdone-universal/)
- [`markdone-universal/deno.json`](markdone-universal/deno.json)
- [`markdone-universal/Containerfile`](markdone-universal/Containerfile)
- [`markdone-universal/podman-kube.yaml`](markdone-universal/podman-kube.yaml)
- [`markdone-universal/setup.sh`](markdone-universal/setup.sh)
- [`markdone-universal/deploy.sh`](markdone-universal/deploy.sh)
- [`markdone-universal/services/high_fidelity_pdf.py`](markdone-universal/services/high_fidelity_pdf.py)
- [`markdone-universal/server.ts`](markdone-universal/server.ts)
- [`markdone-universal/static/index.html`](markdone-universal/static/index.html)
- [`markdone-universal/static/app.js`](markdone-universal/static/app.js)
- [`markdone-universal/README.md`](markdone-universal/README.md)
- [`markdone-universal/tests/integration.ts`](markdone-universal/tests/integration.ts)
- [`markdone-universal/tsconfig.json`](markdone-universal/tsconfig.json)
- [`markdone-universal/.vscode/settings.json`](markdone-universal/.vscode/settings.json)

## Architecture implemented

### Backend
- [`markdone-universal/server.ts`](markdone-universal/server.ts)
  - Deno + Oak server
  - Endpoints:
    - `GET /health`
    - `POST /api/convert`
    - `GET /api/downloads/:fileName`
    - `GET /`
  - Features:
    - file validation
    - bounded concurrency
    - upload persistence
    - cleanup timer
    - graceful shutdown
    - Pandoc invocation via `Deno.Command`
    - Python high-fidelity sidecar invocation via `Deno.Command`

### Python sidecar
- [`markdone-universal/services/high_fidelity_pdf.py`](markdone-universal/services/high_fidelity_pdf.py)
  - Reuses legacy modules from [`pdf-to-obsidian-md-v2/src/`](pdf-to-obsidian-md-v2/src/)
  - Imports:
    - [`PDFExtractor`](pdf-to-obsidian-md-v2/src/pdf_extractor.py)
    - [`ContentCleaner`](pdf-to-obsidian-md-v2/src/content_cleaner.py)
    - [`MarkdownFormatter`](pdf-to-obsidian-md-v2/src/markdown_formatter.py)
    - [`MarkdownCleanup`](pdf-to-obsidian-md-v2/src/markdown_cleanup.py)
  - Depends on [`fitz`](markdone-universal/services/high_fidelity_pdf.py:41), which comes from [`PyMuPDF`](pdf-to-obsidian-md-v2/requirements.txt:7)

### Frontend
- [`markdone-universal/static/index.html`](markdone-universal/static/index.html)
- [`markdone-universal/static/app.js`](markdone-universal/static/app.js)
  - Zero-build UI
  - queue/staging
  - drag-and-drop
  - target/source-type controls
  - YAML frontmatter toggle
  - high-fidelity toggle
  - conversion submission and result tracking

### Deployment
- [`markdone-universal/deploy.sh`](markdone-universal/deploy.sh)
- [`markdone-universal/podman-kube.yaml`](markdone-universal/podman-kube.yaml)
  - Port `7482`
  - HostPath mount for Vault vault:
    - `/Users/<USER>/Documents/VaultVault` → `/app/outputs/obsidian`

## Validation status

### Host environment observations
- `deno` is **not installed or not in PATH** on the host machine.
- Because of that, direct host validation with [`deno check`](markdone-universal/server.ts) was not possible.
- Podman CLI is available:
  - `podman version 5.8.1`

### Podman build debugging history

#### Attempt 1: Alpine + `py3-pymupdf`
- Initial [`markdone-universal/Containerfile`](markdone-universal/Containerfile) used Alpine-based Deno image.
- Failure:
  - Alpine package `py3-pymupdf` not found.

#### Attempt 2: Alpine + pip install
- Changed to pip installation:
  - `pip3 install PyMuPDF==1.23.26`
- Failure:
  - PEP 668 / externally managed environment.

#### Attempt 3: Alpine + `--break-system-packages`
- Changed pip command to:
  - `pip3 install --no-cache-dir --break-system-packages PyMuPDF==1.23.26`
- Failure:
  - missing `make`

#### Attempt 4: Alpine + build tools
- Added build tools:
  - `build-base`
  - `make`
  - `g++`
  - `musl-dev`
  - `linux-headers`
- Failure:
  - very heavy native source build of MuPDF on Alpine/aarch64
  - compile path eventually failed / was killed

#### Attempt 5: Debian-based Deno image
- Switched from Alpine to Debian-based Deno image to avoid musl friction.
- Failure:
  - still fell back to source build
  - missing `make`

#### Attempt 6: Debian + `make` + Python 3.11 pin attempt
Current latest [`markdone-universal/Containerfile`](markdone-universal/Containerfile) was changed to:

- base image: `denoland/deno:debian-2.2.4`
- install:
  - `bash`
  - `make`
  - `pandoc`
  - `python3.11`
  - `python3-pip`
  - `python3-pil`
  - `python3-yaml`
  - `python3-requests`
  - `python3-regex`
  - `python3-lxml`
  - `python3-bs4`
- set alternative:
  - `update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1`
- then:
  - `pip3 install --no-cache-dir --break-system-packages PyMuPDF==1.23.26`

This edit was applied, but the next build was **not executed** because the user asked to save session memory first.

## Current blocker

The main blocker is container installation of [`PyMuPDF==1.23.26`](pdf-to-obsidian-md-v2/requirements.txt:7) on this arm64 environment.

Reasoning so far:
- [`high_fidelity_pdf.py`](markdone-universal/services/high_fidelity_pdf.py:41) imports [`fitz`](markdone-universal/services/high_fidelity_pdf.py:41)
- reused [`PDFExtractor`](pdf-to-obsidian-md-v2/src/pdf_extractor.py:12) also imports [`fitz`](pdf-to-obsidian-md-v2/src/pdf_extractor.py:12)
- so high-fidelity mode currently requires PyMuPDF
- Alpine path is unsuitable due to source build complexity and musl friction
- Debian path is better, but Python version compatibility matters for wheel availability

## Latest known file baseline

### [`markdone-universal/Containerfile`](markdone-universal/Containerfile)
Latest intended baseline after the last applied edit:

```Dockerfile
FROM denoland/deno:debian-2.2.4

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    bash \
    make \
    pandoc \
    python3.11 \
    python3-pip \
    python3-pil \
    python3-yaml \
    python3-requests \
    python3-regex \
    python3-lxml \
    python3-bs4 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    pip3 install --no-cache-dir --break-system-packages PyMuPDF==1.23.26 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN mkdir -p /app/uploads /app/outputs /app/outputs/obsidian /app/static /app/services /app/tests && \
    chown -R deno:deno /app

USER deno

EXPOSE 7482

CMD ["deno", "run", "--allow-all", "server.ts"]
```

## Immediate next step to resume later

From workspace root:
```bash
cd /Users/<USER>/IBM-Bob/MarkDone/markdone-universal
podman build -t localhost/markdone-universal:latest -f ./Containerfile .
```

## If the next build still fails

Recommended troubleshooting order:

1. Check whether [`python3.11`](markdone-universal/Containerfile) really exists in the base image and whether `python3` points to it.
2. If pip still builds from source, install additional Python build helpers or use a dedicated Python 3.11 virtual environment before pip install.
3. If wheel availability is still a problem, consider:
   - using a different Debian-tagged Deno image with older Debian/Python
   - using a multi-stage build with a Python base image for the sidecar dependencies
   - separating the sidecar into a dedicated Python container
4. If needed, reduce risk by temporarily making high-fidelity mode optional and documenting it as a deferred feature, but only if that still aligns with [`markdone-production-spec.md`](markdone-production-spec.md)

## Useful commands to continue later

### Build image
```bash
cd /Users/<USER>/IBM-Bob/MarkDone/markdone-universal
podman build -t localhost/markdone-universal:latest -f ./Containerfile .
```

### Deploy pod
```bash
cd /Users/<USER>/IBM-Bob/MarkDone/markdone-universal
./deploy.sh
```

### Manual deploy alternative
```bash
cd /Users/<USER>/IBM-Bob/MarkDone/markdone-universal
podman kube play --replace ./podman-kube.yaml
```

### Check pod/container status
```bash
podman ps -a
podman pod ps
podman images
```

### View logs
```bash
podman logs <container_name>
```

### Health check
```bash
curl http://localhost:7482/health
```

## Important implementation notes

- [`markdone-universal/podman-kube.yaml`](markdone-universal/podman-kube.yaml) assumes the host vault path exists:
  - `/Users/<USER>/Documents/VaultVault`
- The host currently lacks direct `deno` usage, so containerized validation is the active path.
- `.vscode/**` files were created for local editor support but are excluded from review.

## Reminder checklist state

- [x] Review the implementation plan against production-readiness criteria
- [x] Identify specification gaps, ambiguities, inconsistencies, and blockers
- [x] Assess traceability from business intent to technical specifications
- [x] Determine readiness classification and required remediation level
- [x] Present a concise verdict with prioritized recommendations
- [x] Draft a production-ready specification in [`markdone-production-spec.md`](markdone-production-spec.md)
- [x] Include formal requirements, API contracts, architecture boundaries, and acceptance criteria
- [x] Include security, testing, deployment, operations, and traceability sections
- [x] Revise [`markdone-production-spec.md`](markdone-production-spec.md) for single-user MacBook Pro production readiness
- [x] Ask for approval of the revised specification approach before implementation mode
- [x] Scaffold [`markdone-universal/`](markdone-universal/) infrastructure files
- [x] Implement backend API and Python conversion engine
- [x] Implement frontend staging queue UI
- [x] Add integration test and README
- [-] Validate deployment flow and fix issues
- [ ] Resolve local environment prerequisite blocker: `deno` not installed or not in PATH`

## Resume prompt suggestion

If resuming in a new session, use this prompt:

> Continue implementation and Podman-based validation for [`markdone-universal/`](markdone-universal/) using [`session-memory-markdone.md`](session-memory-markdone.md) as the recovery context. Start by verifying the latest [`markdone-universal/Containerfile`](markdone-universal/Containerfile) baseline, then rerun the Podman build and continue troubleshooting the [`PyMuPDF`](pdf-to-obsidian-md-v2/requirements.txt:7) installation path until the image builds successfully.
