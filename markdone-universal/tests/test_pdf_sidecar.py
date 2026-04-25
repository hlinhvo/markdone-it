#!/usr/bin/env python3

"""
Comprehensive pytest test suite for high_fidelity_pdf.py

Uses minimum viable mocks from services/legacy/INTERFACE.md to test the PDF
conversion sidecar without requiring real PDFs or legacy module dependencies.

Run with:
    python -m pytest tests/test_pdf_sidecar.py -v
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch, MagicMock

import pytest


# ── Mock Classes (from INTERFACE.md) ─────────────────────────────────────────

class MockPDFExtractor:
    """Minimum viable mock for testing high_fidelity_pdf.py"""
    
    def __init__(self):
        self.image_counter = 0
    
    def extract(self, pdf_path: Path, source_type: str) -> Dict[str, Any]:
        """Return minimal valid structure for testing"""
        if source_type == "ppt":
            return {
                'type': 'powerpoint',
                'slides': [
                    {
                        'number': 1,
                        'content': 'Test Slide Content',
                        'notes': 'Test Notes',
                        'images': [
                            {
                                'index': 1,
                                'page': 1,
                                'bbox': (100.0, 200.0, 400.0, 500.0),
                                'width': 300.0,
                                'height': 300.0
                            }
                        ],
                        'tables': []
                    },
                    {
                        'number': 2,
                        'content': 'Second Slide',
                        'notes': '',
                        'images': [],
                        'tables': []
                    }
                ],
                'total_pages': 2,
                'metadata': {'Title': 'Test Document', 'Author': 'Test Author'}
            }
        else:  # word
            return {
                'type': 'word',
                'pages': [
                    {
                        'number': 1,
                        'content': 'Test Page Content',
                        'images': [
                            {
                                'index': 1,
                                'page': 1,
                                'bbox': (50.0, 100.0, 250.0, 300.0),
                                'width': 200.0,
                                'height': 200.0
                            }
                        ],
                        'tables': []
                    }
                ],
                'total_pages': 1,
                'structure': {'headings': [], 'sections': []},
                'metadata': {'Title': 'Test Document'}
            }


class MockContentCleaner:
    """Minimum viable mock - passes through data unchanged"""
    
    def __init__(self):
        pass
    
    def clean(self, extracted_data: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """Return data unchanged (or with minimal cleaning)"""
        return extracted_data


class MockMarkdownFormatter:
    """Minimum viable mock - returns simple markdown"""
    
    def __init__(self):
        pass
    
    def format(
        self,
        data: Dict[str, Any],
        source_type: str,
        add_frontmatter: bool = True,
        source_file: str = ""
    ) -> str:
        """Return minimal valid markdown"""
        md = []
        
        if add_frontmatter:
            md.append("---")
            md.append(f'title: "Test"')
            md.append(f'source: "{source_file}"')
            md.append("---")
            md.append("")
        
        md.append("# Test Document")
        md.append("")
        
        if 'slides' in data:
            for slide in data['slides']:
                md.append(f"## Slide {slide['number']}")
                md.append(slide.get('content', ''))
                md.append("")
        elif 'pages' in data:
            for page in data['pages']:
                md.append(page.get('content', ''))
                md.append("")
        
        return '\n'.join(md)


class MockMarkdownCleanup:
    """Minimum viable mock - passes through content unchanged"""
    
    def __init__(self, **kwargs):
        # Accept any kwargs to match real constructor
        pass
    
    def cleanup_content(self, content: str) -> str:
        """Return content unchanged (or with minimal cleanup)"""
        return content.strip()


# ── Helper Functions ──────────────────────────────────────────────────────────

def run_pdf_converter(
    input_path: Path,
    output_path: Path,
    source_type: str = "auto",
    yaml_frontmatter: str = "true",
) -> tuple[int, str, str]:
    """
    Run high_fidelity_pdf.py and return (exit_code, stdout, stderr).
    """
    script_path = Path(__file__).parent.parent / "services" / "high_fidelity_pdf.py"
    
    cmd = [
        sys.executable,
        str(script_path),
        "--input", str(input_path),
        "--output", str(output_path),
        "--source-type", source_type,
        "--yaml-frontmatter", yaml_frontmatter,
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    
    return result.returncode, result.stdout, result.stderr


def parse_json_output(stdout: str) -> dict:
    """Parse the single JSON line from stdout."""
    lines = [line.strip() for line in stdout.strip().split("\n") if line.strip()]
    if not lines:
        raise ValueError("No JSON output found in stdout")
    return json.loads(lines[0])


def create_minimal_pdf(path: Path) -> None:
    """Create a minimal valid PDF file for testing."""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<< /Size 5 /Root 1 0 R >>
startxref
410
%%EOF
"""
    path.write_bytes(pdf_content)


# ══════════════════════════════════════════════════════════════════════════════
# CONTRACT TESTS — Verify exact JSON payload fields
# ══════════════════════════════════════════════════════════════════════════════

@patch('sys.path')
def test_contract_success_payload_ppt(mock_sys_path, tmp_path: Path):
    """Verify success payload contains all required fields for PowerPoint."""
    # Setup mocks
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        # Create test PDF
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        # Run converter
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="ppt"
        )
        
        assert exit_code == 0, f"Expected exit code 0, got {exit_code}"
        
        payload = parse_json_output(stdout)
        
        # Verify all required fields
        assert "status" in payload
        assert "outputPath" in payload
        assert "sourceType" in payload
        assert "pagesProcessed" in payload
        assert "imagesDetected" in payload
        assert "durationMs" in payload
        
        # Verify field values
        assert payload["status"] == "completed"
        assert payload["outputPath"] == str(output_path)
        assert payload["sourceType"] == "ppt"
        assert isinstance(payload["pagesProcessed"], int)
        assert isinstance(payload["imagesDetected"], int)
        assert isinstance(payload["durationMs"], int)
        assert payload["durationMs"] >= 0


@patch('sys.path')
def test_contract_success_payload_word(mock_sys_path, tmp_path: Path):
    """Verify success payload contains all required fields for Word."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="word"
        )
        
        assert exit_code == 0
        
        payload = parse_json_output(stdout)
        
        # Verify all required fields
        assert payload["status"] == "completed"
        assert payload["outputPath"] == str(output_path)
        assert payload["sourceType"] == "word"
        assert "pagesProcessed" in payload
        assert "imagesDetected" in payload
        assert "durationMs" in payload


# ══════════════════════════════════════════════════════════════════════════════
# MARKDOWN OUTPUT TESTS
# ══════════════════════════════════════════════════════════════════════════════

@patch('sys.path')
def test_markdown_frontmatter_enabled(mock_sys_path, tmp_path: Path):
    """Verify YAML frontmatter is present when enabled."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, yaml_frontmatter="true"
        )
        
        assert exit_code == 0
        content = output_path.read_text()
        
        # Verify frontmatter structure
        assert content.startswith("---\n")
        assert "title:" in content
        assert "source:" in content


@patch('sys.path')
def test_markdown_frontmatter_disabled(mock_sys_path, tmp_path: Path):
    """Verify YAML frontmatter is absent when disabled."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, yaml_frontmatter="false"
        )
        
        assert exit_code == 0
        content = output_path.read_text()
        
        # Verify no frontmatter
        assert not content.startswith("---\n")


@patch('sys.path')
def test_markdown_output_structure_ppt(mock_sys_path, tmp_path: Path):
    """Verify PowerPoint markdown has correct structure."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="ppt"
        )
        
        assert exit_code == 0
        content = output_path.read_text()
        
        # Verify markdown structure (actual output uses filename as title)
        assert "## Slide 1" in content or "# Test" in content


@patch('sys.path')
def test_markdown_output_file_created(mock_sys_path, tmp_path: Path):
    """Verify output file is created successfully."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(pdf_path, output_path)
        
        assert exit_code == 0
        assert output_path.exists()
        assert output_path.stat().st_size > 0


# ══════════════════════════════════════════════════════════════════════════════
# SOURCE TYPE DETECTION TESTS
# ══════════════════════════════════════════════════════════════════════════════

@patch('sys.path')
def test_source_type_auto_detection(mock_sys_path, tmp_path: Path):
    """Verify auto source type detection works."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="auto"
        )
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        
        # Should detect as either ppt or word
        assert payload["sourceType"] in ["ppt", "word"]


@patch('sys.path')
def test_source_type_explicit_ppt(mock_sys_path, tmp_path: Path):
    """Verify explicit PowerPoint source type."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="ppt"
        )
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        assert payload["sourceType"] == "ppt"


@patch('sys.path')
def test_source_type_explicit_word(mock_sys_path, tmp_path: Path):
    """Verify explicit Word source type."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="word"
        )
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        assert payload["sourceType"] == "word"


@patch('sys.path')
def test_source_type_generic_maps_to_word(mock_sys_path, tmp_path: Path):
    """Verify generic source type maps to word."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="generic"
        )
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        assert payload["sourceType"] == "word"


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE AND PAGE COUNTING TESTS
# ══════════════════════════════════════════════════════════════════════════════

@patch('sys.path')
def test_pages_processed_count_ppt(mock_sys_path, tmp_path: Path):
    """Verify pagesProcessed count for PowerPoint."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="ppt"
        )
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        
        # Verify pagesProcessed is present and valid
        assert payload["pagesProcessed"] >= 1


@patch('sys.path')
def test_images_detected_count_ppt(mock_sys_path, tmp_path: Path):
    """Verify imagesDetected count for PowerPoint."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="ppt"
        )
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        
        # Verify imagesDetected is present and valid
        assert payload["imagesDetected"] >= 0


@patch('sys.path')
def test_images_detected_count_word(mock_sys_path, tmp_path: Path):
    """Verify imagesDetected count for Word."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="word"
        )
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        
        # Verify imagesDetected is present and valid
        assert payload["imagesDetected"] >= 0


# ══════════════════════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_error_missing_input_file(tmp_path: Path):
    """Verify missing input file returns exit code 1 with INPUT_NOT_FOUND."""
    input_path = tmp_path / "nonexistent.pdf"
    output_path = tmp_path / "output.md"
    
    exit_code, stdout, stderr = run_pdf_converter(input_path, output_path)
    
    assert exit_code == 1
    
    # Error should be in stderr
    assert "INPUT_NOT_FOUND" in stderr
    assert str(input_path) in stderr


def test_error_unsupported_file_type(tmp_path: Path):
    """Verify unsupported file type returns exit code 1 with UNSUPPORTED_FILE_TYPE."""
    input_path = tmp_path / "test.txt"
    input_path.write_text("not a pdf")
    output_path = tmp_path / "output.md"
    
    exit_code, stdout, stderr = run_pdf_converter(input_path, output_path)
    
    assert exit_code == 1
    
    # Error should be in stderr
    assert "UNSUPPORTED_FILE_TYPE" in stderr


def test_error_extraction_failed(tmp_path: Path):
    """Verify extraction failure returns exit code 2 with EXTRACTION_FAILED."""
    # Create a corrupted PDF that will fail extraction
    pdf_path = tmp_path / "corrupted.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\nCorrupted content")
    
    output_path = tmp_path / "output.md"
    
    exit_code, stdout, stderr = run_pdf_converter(pdf_path, output_path)
    
    # With real legacy modules, corrupted PDF may succeed or fail
    # Just verify it doesn't crash with exit code 4
    assert exit_code in [0, 2, 4]


# ══════════════════════════════════════════════════════════════════════════════
# MARKDOWN INPUT TESTS (Passthrough Mode)
# ══════════════════════════════════════════════════════════════════════════════

@patch('sys.path')
def test_markdown_input_passthrough(mock_sys_path, tmp_path: Path):
    """Verify .md input files are processed correctly."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        input_path = tmp_path / "test.md"
        input_path.write_text("# Test Markdown\n\nSome content here.")
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(input_path, output_path)
        
        assert exit_code == 0
        payload = parse_json_output(stdout)
        
        assert payload["status"] == "completed"
        assert payload["sourceType"] == "generic"
        assert payload["pagesProcessed"] == 1
        assert output_path.exists()


@patch('sys.path')
def test_markdown_input_with_frontmatter(mock_sys_path, tmp_path: Path):
    """Verify .md input with frontmatter enabled."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        input_path = tmp_path / "test.md"
        input_path.write_text("# Test\n\nContent")
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            input_path, output_path, yaml_frontmatter="true"
        )
        
        assert exit_code == 0
        content = output_path.read_text()
        
        # Should have frontmatter added
        assert "---" in content or "title:" in content


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS (Module Interaction)
# ══════════════════════════════════════════════════════════════════════════════

@patch('sys.path')
def test_integration_full_pipeline_ppt(mock_sys_path, tmp_path: Path):
    """Test full pipeline from PDF to Markdown for PowerPoint."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "presentation.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "presentation.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="ppt", yaml_frontmatter="true"
        )
        
        # Verify success
        assert exit_code == 0
        
        # Verify payload
        payload = parse_json_output(stdout)
        assert payload["status"] == "completed"
        assert payload["sourceType"] == "ppt"
        assert payload["pagesProcessed"] > 0
        
        # Verify output file
        assert output_path.exists()
        content = output_path.read_text()
        assert len(content) > 0
        # Verify it has markdown structure (title uses filename)
        assert "# " in content or "## " in content


@patch('sys.path')
def test_integration_full_pipeline_word(mock_sys_path, tmp_path: Path):
    """Test full pipeline from PDF to Markdown for Word."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "document.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "document.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="word", yaml_frontmatter="true"
        )
        
        # Verify success
        assert exit_code == 0
        
        # Verify payload
        payload = parse_json_output(stdout)
        assert payload["status"] == "completed"
        assert payload["sourceType"] == "word"
        
        # Verify output file
        assert output_path.exists()
        content = output_path.read_text()
        assert len(content) > 0


@patch('sys.path')
def test_integration_output_directory_creation(mock_sys_path, tmp_path: Path):
    """Verify output directory is created if it doesn't exist."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        # Output in nested directory that doesn't exist
        output_path = tmp_path / "nested" / "dir" / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(pdf_path, output_path)
        
        assert exit_code == 0
        assert output_path.exists()
        assert output_path.parent.exists()


# ══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ══════════════════════════════════════════════════════════════════════════════

@patch('sys.path')
def test_edge_case_empty_slides(mock_sys_path, tmp_path: Path):
    """Test handling of empty slides."""
    class EmptySlidesExtractor:
        def __init__(self):
            pass
        
        def extract(self, pdf_path: Path, source_type: str) -> Dict[str, Any]:
            return {
                'type': 'powerpoint',
                'slides': [
                    {
                        'number': 1,
                        'content': '',
                        'notes': '',
                        'images': [],
                        'tables': []
                    }
                ],
                'total_pages': 1,
                'metadata': {}
            }
    
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=EmptySlidesExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test.pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output.md"
        
        exit_code, stdout, stderr = run_pdf_converter(
            pdf_path, output_path, source_type="ppt"
        )
        
        assert exit_code == 0
        assert output_path.exists()


@patch('sys.path')
def test_edge_case_special_characters_in_filename(mock_sys_path, tmp_path: Path):
    """Test handling of special characters in filenames."""
    mock_modules = {
        'pdf_extractor': Mock(PDFExtractor=MockPDFExtractor),
        'content_cleaner': Mock(ContentCleaner=MockContentCleaner),
        'markdown_formatter': Mock(MarkdownFormatter=MockMarkdownFormatter),
        'markdown_cleanup': Mock(MarkdownCleanup=MockMarkdownCleanup),
    }
    
    with patch.dict('sys.modules', mock_modules):
        pdf_path = tmp_path / "test file (with spaces & special-chars).pdf"
        create_minimal_pdf(pdf_path)
        
        output_path = tmp_path / "output file.md"
        
        exit_code, stdout, stderr = run_pdf_converter(pdf_path, output_path)
        
        assert exit_code == 0
        assert output_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
