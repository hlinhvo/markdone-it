# Changelog

All notable changes to MarkDone v2 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Real-time Progress Tracking via SSE**: Large file conversions (50+ page PDFs, multi-sheet XLSX) now display live progress updates with percentage and page/sheet numbers
  - New SSE endpoint `/api/convert/progress/:conversionId` for streaming progress events
  - Visual progress bar component in UI with smooth animations
  - Progress callbacks in Python conversion scripts emit JSON events to stderr
  - EventSource-based frontend connection for push-based updates
  - Automatic cleanup of stale SSE connections after 5 minutes of inactivity

### Changed
- **Security Hardening - Restricted Deno Permissions**: Replaced `--allow-all` flag with minimal required permissions following principle of least privilege
  - `--allow-net`: Network access for HTTP server
  - `--allow-read`: File system read access
  - `--allow-write`: File system write access  
  - `--allow-env`: Environment variable access
  - `--allow-run=python3,pandoc`: Restricted subprocess execution to only required binaries
  - Applied across all deployment configurations (deno.json, Containerfile, README)

### Fixed
- **Stderr Lock Error**: Fixed "Cannot collect output: 'stderr' is locked" error during conversions
  - Root cause: Attempting to read `proc.stderr` twice (streaming + `proc.output()`)
  - Solution: Manually collect stdout/stderr chunks while streaming instead of using `proc.output()`
  - Affected functions: `convertPdfToMarkdown()` and `convertXlsxToMarkdown()` in server.ts
  
- **Progress Events Not Emitting**: Fixed progress bar showing 0% then jumping to 100% without intermediate updates
  - Root cause: Python scripts redirected `sys.stdout` to `sys.stderr`, causing `emit_progress()` to write to wrong stream
  - Solution: Preserve real stderr file descriptor before redirection and write progress events directly to it
  - Affected files: `high_fidelity_pdf.py` and `xlsx_converter.py`

### Documentation
- Added `docs/implementation-plan-sse-permissions.md` - Complete implementation plan for SSE and security features
- Added `docs/deployment-verification.md` - Verification of deployment scripts with new directory structure
- Added `docs/sse-stderr-lock-fix.md` - Detailed explanation of stderr locking issue and resolution
- Added `docs/progress-emission-fix.md` - Detailed explanation of progress emission issue with stream flow diagrams
- Updated `markdone-universal/README.md` with Security section, Progress Tracking section, and updated API documentation

## Technical Details

### SSE Architecture
```
Frontend (EventSource) ←─ SSE ─→ Deno Server ←─ stderr ─→ Python Process
                                      ↓
                                 Progress Relay
                                      ↓
                              Active Connections Map
```

### Stream Flow (After Fix)
```
Python Process:
  stdout (fd 1) ──> _real_stdout ──> Deno stdout reader (JSON result)
  stdout (fd 1) ──> sys.stderr   ──> (library noise only)
  stderr (fd 2) ──> _real_stderr ──> Deno stderr reader (progress JSON)
```

### Files Modified
- `markdone-universal/server.ts` - SSE endpoint, progress relay, stream collection fixes
- `markdone-universal/services/high_fidelity_pdf.py` - Progress emission and stderr preservation
- `markdone-universal/services/legacy/pdf_extractor.py` - Progress callback support
- `markdone-universal/services/xlsx_converter.py` - Progress emission and stderr preservation
- `markdone-universal/static/index.html` - Progress bar CSS
- `markdone-universal/static/app.js` - EventSource connection and progress rendering
- `markdone-universal/deno.json` - Restricted permissions
- `markdone-universal/Containerfile` - Restricted permissions
- `markdone-universal/README.md` - Security and progress documentation

### Testing Recommendations
1. Upload a 50+ page PDF and verify smooth progress updates (10%, 20%, 30%...)
2. Upload a multi-sheet XLSX file and verify per-sheet progress tracking
3. Verify all conversion types work with new restricted permissions
4. Confirm no permission errors occur during normal operations
5. Test error handling - verify error messages still display correctly

---

## [2.0.0] - 2024-01-XX (Initial Release)

### Added
- Complete rewrite from v1 to v2 architecture
- Deno 2.x TypeScript orchestrator
- Python sidecar services for PDF and XLSX conversion
- High-fidelity PDF extraction with PowerPoint/Word detection
- XLSX to Markdown/JSON conversion
- Obsidian Vault integration
- RESTful API with file upload
- Modern web UI with drag-and-drop
- Container deployment with Podman/Kubernetes
- Comprehensive test suite

See `COMMIT_HISTORY.md` for detailed commit-by-commit breakdown of initial release.