# MarkDone v2

A production-ready document conversion tool for converting PDFs to Markdown and other formats.

## Project Structure

```
MarkDone-v2/
├── docs/                           # Project documentation
│   ├── markdone-production-spec.md # Production specification
│   ├── implementation-plan-markdone # Implementation plan
│   └── session-memory-markdone.md  # Development session notes
├── markdone-universal/             # Main application
│   ├── services/                   # Conversion services
│   │   ├── high_fidelity_pdf.py   # High-fidelity PDF converter
│   │   ├── xlsx_converter.py      # Excel converter
│   │   └── legacy/                # Legacy conversion modules
│   ├── static/                     # Frontend assets
│   │   ├── index.html             # Main UI
│   │   └── app.js                 # Frontend logic
│   ├── tests/                      # Test suite
│   ├── server.ts                   # Deno backend server
│   ├── Containerfile              # Container image definition
│   ├── podman-kube.yaml           # Kubernetes/Podman deployment
│   ├── deploy.sh                  # Deployment script
│   ├── setup.sh                   # Setup script
│   └── README.md                  # Application documentation
└── outputs/                        # Output directory
    └── vault/                      # Vault/Obsidian output

```

## Quick Start

See [`markdone-universal/README.md`](markdone-universal/README.md) for detailed setup and usage instructions.

### Prerequisites

- macOS (MacBook Pro 16 recommended)
- Podman Desktop 1.26+
- Deno 2.x

### Setup

```bash
cd markdone-universal
chmod +x ./setup.sh ./deploy.sh
./setup.sh
```

### Development

```bash
cd markdone-universal
deno task dev
```

Access the UI at: `http://127.0.0.1:7482`

### Production Deployment

```bash
cd markdone-universal
./deploy.sh
```

## Documentation

- **[Production Specification](docs/markdone-production-spec.md)** - Complete technical specification
- **[Implementation Plan](docs/implementation-plan-markdone)** - Development roadmap
- **[Session Memory](docs/session-memory-markdone.md)** - Development notes and decisions

## Features

- High-fidelity PDF to Markdown conversion
- Batch processing with drag-and-drop interface
- Multiple output formats (Markdown, HTML, DOCX, PDF)
- YAML frontmatter support for Markdown
- Local-first architecture
- Podman containerized deployment
- Resource-efficient (Sleep/Burst modes)

## Architecture

- **Backend**: Deno 2.x + Oak framework
- **Frontend**: Preact + HTM (zero-build)
- **Styling**: Pico CSS with IBM Carbon design
- **Conversion Engine**: Python (PyMuPDF) + Pandoc
- **Deployment**: Podman Kube Play

## License

Internal use only.