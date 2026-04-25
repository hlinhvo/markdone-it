#!/usr/bin/env python3

"""
MarkDone XLSX conversion sidecar.

Converts Excel workbooks (.xlsx) to Markdown tables (vault_md) or structured
JSON (vault_json).  Follows the same CLI contract as high_fidelity_pdf.py so
the Deno orchestrator can spawn it identically:

  stdout  → single JSON line (success payload or nothing)
  stderr  → all logging, warnings, library noise
  exit 0  → completed
  exit 1  → INPUT_NOT_FOUND
  exit 2  → EXTRACTION_FAILED
  exit 3  → OUTPUT_WRITE_FAILED
  exit 4  → INTERNAL_ERROR

CLI
───
  python3 xlsx_converter.py \
    --input  path/to/file.xlsx \
    --output path/to/file.md   \   # or .json for vault_json target
    --target vault_md              # vault_md | vault_json
    --yaml-frontmatter true        # only applies to vault_md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Protect stdout from library noise (same pattern as high_fidelity_pdf.py) ─
_real_stdout_fd = os.dup(sys.stdout.fileno())
_real_stdout = os.fdopen(_real_stdout_fd, "w")
sys.stdout = sys.stderr  # redirect all print() / warnings → stderr

import openpyxl  # noqa: E402
import pandas as pd  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────

COMPLIANCE_KEYWORDS = {
    "requirement", "compliance", "response", "status",
    "vendor", "remarks", "criteria", "mandatory", "comment",
    "answer", "evidence", "met", "partially", "score",
}

MAX_CELL_LENGTH = 500       # truncate runaway cells in Markdown output
MAX_ROWS_PER_SHEET = 2000   # safety cap per sheet


# ── Helpers ───────────────────────────────────────────────────────────────────

def emit_json(data: dict) -> None:
    """Write exactly one JSON line to the real stdout for Deno to parse."""
    _real_stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    _real_stdout.flush()


def str_to_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {value!r}")


def detect_sheet_type(df: pd.DataFrame) -> str:
    """
    Return 'compliance' when column headers overlap with compliance keywords,
    otherwise return 'generic'.
    """
    headers = {str(c).strip().lower() for c in df.columns}
    overlap = headers & COMPLIANCE_KEYWORDS
    return "compliance" if len(overlap) >= 2 else "generic"


def clean_cell(value: Any) -> str:
    """Stringify a cell value, collapsing whitespace and capping length."""
    if pd.isna(value):
        return ""
    text = str(value).strip().replace("\n", " ").replace("|", "\\|")
    if len(text) > MAX_CELL_LENGTH:
        text = text[:MAX_CELL_LENGTH] + "…"
    return text


def df_to_markdown_table(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a GitHub-flavoured Markdown table."""
    if df.empty:
        return "_No data_\n"

    # Cap rows
    df = df.head(MAX_ROWS_PER_SHEET)

    headers = [clean_cell(c) for c in df.columns]
    separator = ["---"] * len(headers)

    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(separator) + " |")

    for _, row in df.iterrows():
        cells = [clean_cell(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"


def df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of dicts, replacing NaN with None."""
    df = df.head(MAX_ROWS_PER_SHEET)
    return [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for _, row in df.iterrows()
    ]


def build_yaml_frontmatter(source_file: str, sheets: list[str], sheet_types: dict[str, str]) -> str:
    return (
        "---\n"
        f"title: \"{Path(source_file).stem}\"\n"
        f"source: \"{source_file}\"\n"
        f"lang: en\n"
        f"converted_at: \"{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\"\n"
        f"sheets: {json.dumps(sheets)}\n"
        f"sheet_types: {json.dumps(sheet_types)}\n"
        "---\n\n"
    )


# ── Core conversion ───────────────────────────────────────────────────────────

def convert_to_markdown(
    input_path: Path,
    output_path: Path,
    yaml_frontmatter: bool,
) -> dict:
    """Read all sheets, emit a single Markdown file with one section per sheet."""
    wb = openpyxl.load_workbook(str(input_path), read_only=True, data_only=True)
    sheet_names = wb.sheetnames
    wb.close()

    sections: list[str] = []
    sheet_types: dict[str, str] = {}
    total_rows = 0

    for sheet_name in sheet_names:
        try:
            df = pd.read_excel(str(input_path), sheet_name=sheet_name, dtype=str)
        except Exception as exc:
            # Skip sheets that can't be parsed (charts, protected, etc.)
            print(f"[xlsx_converter] Skipping sheet {sheet_name!r}: {exc}", file=sys.stderr)
            continue

        # Drop entirely empty rows and columns
        df.dropna(how="all", inplace=True)
        df.dropna(axis=1, how="all", inplace=True)

        if df.empty:
            continue

        sheet_type = detect_sheet_type(df)
        sheet_types[sheet_name] = sheet_type
        total_rows += min(len(df), MAX_ROWS_PER_SHEET)

        badge = " _(compliance matrix)_" if sheet_type == "compliance" else ""
        section = f"## {sheet_name}{badge}\n\n{df_to_markdown_table(df)}"
        sections.append(section)

    if not sections:
        raise RuntimeError("No readable sheet data found in workbook")

    body = "\n\n".join(sections)

    if yaml_frontmatter:
        frontmatter = build_yaml_frontmatter(input_path.name, sheet_names, sheet_types)
        content = frontmatter + f"# {input_path.stem}\n\n" + body + "\n"
    else:
        content = f"# {input_path.stem}\n\n" + body + "\n"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return {
        "status": "completed",
        "outputPath": str(output_path),
        "sourceType": "xlsx",
        "sheetsProcessed": len(sheet_types),
        "sheetTypes": sheet_types,
        "rowsProcessed": total_rows,
    }


def convert_to_json(
    input_path: Path,
    output_path: Path,
) -> dict:
    """Read all sheets, emit a structured JSON file — most token-efficient for RAG."""
    wb = openpyxl.load_workbook(str(input_path), read_only=True, data_only=True)
    sheet_names = wb.sheetnames
    wb.close()

    workbook_data: dict[str, Any] = {
        "source": input_path.name,
        "lang": "en",
        "converted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sheets": {},
    }

    sheet_types: dict[str, str] = {}
    total_rows = 0

    for sheet_name in sheet_names:
        try:
            df = pd.read_excel(str(input_path), sheet_name=sheet_name, dtype=str)
        except Exception as exc:
            print(f"[xlsx_converter] Skipping sheet {sheet_name!r}: {exc}", file=sys.stderr)
            continue

        df.dropna(how="all", inplace=True)
        df.dropna(axis=1, how="all", inplace=True)

        if df.empty:
            continue

        sheet_type = detect_sheet_type(df)
        sheet_types[sheet_name] = sheet_type
        records = df_to_records(df)
        total_rows += len(records)

        workbook_data["sheets"][sheet_name] = {
            "type": sheet_type,
            "columns": list(df.columns),
            "row_count": len(records),
            "rows": records,
        }

    if not workbook_data["sheets"]:
        raise RuntimeError("No readable sheet data found in workbook")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(workbook_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": "completed",
        "outputPath": str(output_path),
        "sourceType": "xlsx",
        "sheetsProcessed": len(sheet_types),
        "sheetTypes": sheet_types,
        "rowsProcessed": total_rows,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MarkDone XLSX → Markdown / JSON converter")
    parser.add_argument("--input",  required=True, help="Path to input .xlsx file")
    parser.add_argument("--output", required=True, help="Path to output .md or .json file")
    parser.add_argument(
        "--target",
        default="vault_md",
        choices=["vault_md", "vault_json"],
        help="Output target format",
    )
    parser.add_argument(
        "--yaml-frontmatter",
        default="true",
        type=str_to_bool,
        help="Emit YAML frontmatter block (vault_md only)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path  = Path(args.input)
    output_path = Path(args.output)
    started     = time.time()

    # ── Validate input ────────────────────────────────────────────────────────
    if not input_path.exists():
        print(
            json.dumps({
                "status": "failed",
                "error": {
                    "code": "INPUT_NOT_FOUND",
                    "message": f"Input file not found: {input_path}",
                },
            }),
            file=sys.stderr,
        )
        return 1

    if input_path.suffix.lower() not in {".xlsx", ".xlsm"}:
        print(
            json.dumps({
                "status": "failed",
                "error": {
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "message": "Only .xlsx and .xlsm files are supported",
                },
            }),
            file=sys.stderr,
        )
        return 1

    # ── Convert ───────────────────────────────────────────────────────────────
    try:
        if args.target == "vault_json":
            result = convert_to_json(input_path, output_path)
        else:
            result = convert_to_markdown(input_path, output_path, args.yaml_frontmatter)

        result["durationMs"] = int((time.time() - started) * 1000)
        emit_json(result)
        return 0

    except RuntimeError as exc:
        print(
            json.dumps({
                "status": "failed",
                "error": {"code": "EXTRACTION_FAILED", "message": str(exc)},
            }),
            file=sys.stderr,
        )
        return 2

    except OSError as exc:
        print(
            json.dumps({
                "status": "failed",
                "error": {"code": "OUTPUT_WRITE_FAILED", "message": str(exc)},
            }),
            file=sys.stderr,
        )
        return 3

    except Exception as exc:
        print(
            json.dumps({
                "status": "failed",
                "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
            }),
            file=sys.stderr,
        )
        return 4


if __name__ == "__main__":
    raise SystemExit(main())

# Made with Bob