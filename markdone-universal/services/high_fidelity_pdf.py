#!/usr/bin/env python3
"""
MarkDone high-fidelity PDF conversion sidecar.

This script reuses the existing PDF extraction and markdown processing logic from
the legacy project while exposing a simple CLI contract for the Deno orchestrator.
"""

from __future__ import annotations

import argparse
import json
import io
import os
import sys
import time
from pathlib import Path

# ── Protect stdout from legacy module pollution ──────────────────────────────
# The Deno orchestrator parses stdout as JSON.  Legacy modules (loguru,
# PyMuPDF, click, tqdm …) sometimes print warnings / banners to stdout.
# We redirect sys.stdout → stderr so only our explicit JSON output reaches
# the real stdout.
_real_stdout_fd = os.dup(sys.stdout.fileno())   # keep the real fd
_real_stdout = os.fdopen(_real_stdout_fd, "w")   # wrap it in a file object
_real_stderr_fd = os.dup(sys.stderr.fileno())   # keep the real stderr fd
_real_stderr = os.fdopen(_real_stderr_fd, "w")   # wrap it in a file object
sys.stdout = sys.stderr                          # everything else → stderr

LEGACY_SRC = Path(__file__).resolve().parent / "legacy"

if str(LEGACY_SRC) not in sys.path:
    sys.path.insert(0, str(LEGACY_SRC))

from pdf_extractor import PDFExtractor  # type: ignore  # noqa: E402
from content_cleaner import ContentCleaner  # type: ignore  # noqa: E402
from markdown_formatter import MarkdownFormatter  # type: ignore  # noqa: E402
from markdown_cleanup import MarkdownCleanup  # type: ignore  # noqa: E402


def emit_json(data: dict) -> None:
    """Write JSON to the *real* stdout so Deno can parse it."""
    _real_stdout.write(json.dumps(data) + "\n")
    _real_stdout.flush()


def emit_progress(current: int, total: int, message: str = "") -> None:
    """Emit progress event to stderr for Deno to capture via SSE."""
    progress_data = {
        "type": "progress",
        "progress": int((current / total) * 100) if total > 0 else 0,
        "current": current,
        "total": total,
        "message": message or f"Processing page {current}/{total}"
    }
    # Emit to the REAL stderr (not the redirected stdout)
    _real_stderr.write(json.dumps(progress_data) + "\n")
    _real_stderr.flush()


def str_to_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


def detect_source_type(input_path: Path) -> str:
    extractor = PDFExtractor()
    try:
        import fitz  # type: ignore

        doc = fitz.open(str(input_path))
        sample_pages = min(3, len(doc))
        text_samples = []
        for index in range(sample_pages):
            page = doc.load_page(index)
            text_samples.append(page.get_text("text") or "")
        doc.close()

        combined_text = "\n".join(text_samples)
        ppt_indicators = [
            "Slide ",
            "Notes:",
            "Speaker Notes",
        ]
        word_indicators = [
            "Page ",
            "Chapter ",
            "Section ",
        ]
        ppt_score = sum(1 for item in ppt_indicators if item.lower() in combined_text.lower())
        word_score = sum(1 for item in word_indicators if item.lower() in combined_text.lower())
        return "ppt" if ppt_score > word_score else "word"
    except Exception:
        return "word"


def build_markdown(input_path: Path, output_path: Path, source_type: str, yaml_frontmatter: bool) -> dict:
    effective_source_type = detect_source_type(input_path) if source_type == "auto" else source_type

    # Get total pages first for progress reporting
    import fitz
    try:
        doc = fitz.open(str(input_path))
        total_pages = len(doc)
        doc.close()
    except Exception:
        total_pages = 0

    extractor = PDFExtractor()
    cleaner = ContentCleaner()
    formatter = MarkdownFormatter()
    cleanup = MarkdownCleanup(
        remove_duplicate_lines=True,
        standardize_headings=True,
        fix_lists=True,
        normalize_spacing=True,
        add_metadata=False,
        verbose=False,
    )

    # Emit initial progress
    if total_pages > 0:
        emit_progress(0, total_pages, "Starting extraction")

    extracted_data = extractor.extract(input_path, effective_source_type, progress_callback=lambda current, total: emit_progress(current, total))
    if not extracted_data:
        raise RuntimeError("Failed to extract content from PDF")

    # Emit progress for cleaning phase
    if total_pages > 0:
        emit_progress(total_pages, total_pages, "Cleaning content")

    cleaned_data = cleaner.clean(extracted_data, effective_source_type)
    markdown = formatter.format(
        cleaned_data,
        source_type=effective_source_type,
        add_frontmatter=yaml_frontmatter,
        source_file=input_path.name,
    )
    markdown = cleanup.cleanup_content(markdown)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    pages_processed = cleaned_data.get("total_pages", 0)
    images_detected = 0
    if "slides" in cleaned_data:
        images_detected = sum(len(slide.get("images", [])) for slide in cleaned_data["slides"])
    elif "pages" in cleaned_data:
        images_detected = sum(len(page.get("images", [])) for page in cleaned_data["pages"])

    return {
        "status": "completed",
        "outputPath": str(output_path),
        "sourceType": effective_source_type,
        "pagesProcessed": pages_processed,
        "imagesDetected": images_detected,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="High-fidelity PDF to Markdown converter")
    parser.add_argument("--input", required=True, help="Path to input PDF file")
    parser.add_argument("--output", required=True, help="Path to output Markdown file")
    parser.add_argument(
        "--source-type",
        default="auto",
        choices=["auto", "ppt", "word", "generic"],
        help="Detected or explicit source type",
    )
    parser.add_argument(
        "--yaml-frontmatter",
        default="true",
        type=str_to_bool,
        help="Whether YAML frontmatter should be emitted",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    started = time.time()

    if not input_path.exists():
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": "INPUT_NOT_FOUND",
                        "message": f"Input file not found: {input_path}",
                    },
                }
            ),
            file=sys.stderr,
        )
        return 1

    if input_path.suffix.lower() not in [".pdf", ".md", ".markdown"]:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": "UNSUPPORTED_FILE_TYPE",
                        "message": "Only PDF and Markdown inputs are supported by the high-fidelity engine",
                    },
                }
            ),
            file=sys.stderr,
        )
        return 1

    source_type = "word" if args.source_type == "generic" else args.source_type

    try:
        if input_path.suffix.lower() in [".md", ".markdown"]:
            text = input_path.read_text(encoding="utf-8")
            cleanup = MarkdownCleanup(
                remove_duplicate_lines=True,
                standardize_headings=True,
                fix_lists=True,
                normalize_spacing=True,
                add_metadata=False,
                verbose=False,
            )
            
            if args.yaml_frontmatter:
                formatter = MarkdownFormatter()
                # Dummy dict structure for MarkdownFormatter
                text = formatter.format(
                    {"text": text, "metadata": {"title": input_path.stem}},
                    source_type="generic",
                    add_frontmatter=True,
                    source_file=input_path.name,
                )
            
            cleaned_text = cleanup.cleanup_content(text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(cleaned_text, encoding="utf-8")
            
            result = {
                "status": "completed",
                "outputPath": str(output_path),
                "sourceType": "generic",
                "pagesProcessed": 1,
                "imagesDetected": 0,
            }
        else:
            result = build_markdown(
                input_path=input_path,
                output_path=output_path,
                source_type=source_type,
                yaml_frontmatter=args.yaml_frontmatter,
            )
            
        result["durationMs"] = int((time.time() - started) * 1000)
        emit_json(result)
        return 0
    except RuntimeError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": "EXTRACTION_FAILED",
                        "message": str(exc),
                    },
                }
            ),
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": "OUTPUT_WRITE_FAILED",
                        "message": str(exc),
                    },
                }
            ),
            file=sys.stderr,
        )
        return 3
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": str(exc),
                    },
                }
            ),
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())

# Made with Bob
