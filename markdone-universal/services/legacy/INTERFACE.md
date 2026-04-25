# Legacy Module Interface Documentation

This document defines the exact interface contracts for all legacy modules used by `high_fidelity_pdf.py`. Use this as the authoritative reference when mocking, testing, or replacing these modules.

---

## PART 1: AUDIT SUMMARY

### Module Usage Analysis

#### 1. PDFExtractor (`pdf_extractor.py`)

**Methods Called:**
- `__init__()` - Constructor (no parameters)
- `extract(pdf_path: Path, source_type: str) -> Dict[str, Any]`

**Inputs:**
- `pdf_path`: Path object pointing to the PDF file
- `source_type`: String, one of `"ppt"`, `"word"`, or `"generic"`

**Output Structure:**
```python
# For PowerPoint (source_type="ppt"):
{
    'type': 'powerpoint',
    'slides': [
        {
            'number': int,           # 1-based slide number
            'content': str,          # Main slide text
            'notes': str,            # Speaker notes
            'images': [              # List of image metadata
                {
                    'index': int,
                    'page': int,
                    'bbox': tuple,   # (x0, y0, x1, y1)
                    'width': float,
                    'height': float
                }
            ],
            'tables': List[List[str]]  # Optional, 2D array of table data
        }
    ],
    'total_pages': int,
    'metadata': dict             # PDF metadata (Author, Title, etc.)
}

# For Word (source_type="word"):
{
    'type': 'word',
    'pages': [
        {
            'number': int,           # 1-based page number
            'content': str,          # Page text
            'images': [...],         # Same structure as slides
            'tables': List[List[str]]
        }
    ],
    'total_pages': int,
    'structure': {               # Document structure detection
        'headings': [
            {
                'line': int,
                'text': str,
                'level': int
            }
        ],
        'sections': []
    },
    'metadata': dict
}
```

**Filesystem Access:** ✅ YES - Opens and reads PDF files using PyMuPDF

**Risk Level:** 🔴 **HIGH** - Core extraction logic, depends on PyMuPDF, handles file I/O

---

#### 2. ContentCleaner (`content_cleaner.py`)

**Methods Called:**
- `__init__()` - Constructor (no parameters)
- `clean(extracted_data: Dict[str, Any], source_type: str) -> Dict[str, Any]`

**Inputs:**
- `extracted_data`: Dictionary returned by `PDFExtractor.extract()`
- `source_type`: String, one of `"ppt"`, `"word"`, or `"generic"`

**Output Structure:**
```python
# Returns the SAME structure as input, but with cleaned text fields
# For PowerPoint:
{
    'type': 'powerpoint',
    'slides': [
        {
            'number': int,
            'content': str,          # CLEANED text (artifacts removed)
            'notes': str,            # CLEANED text
            'images': [...],         # Unchanged
            'tables': List[List[str]]  # CLEANED (whitespace normalized)
        }
    ],
    'total_pages': int,
    'metadata': dict
}

# For Word:
{
    'type': 'word',
    'pages': [
        {
            'number': int,
            'content': str,          # CLEANED text
            'images': [...],         # Unchanged
            'tables': List[List[str]]  # CLEANED
        }
    ],
    'total_pages': int,
    'structure': {...},              # Unchanged
    'metadata': dict
}
```

**Cleaning Operations:**
- Removes form feeds, page breaks, zero-width characters
- Removes slide/page numbers and navigation artifacts
- Removes header/footer patterns
- Normalizes whitespace and fixes OCR errors
- Cleans table cells

**Filesystem Access:** ❌ NO - Pure in-memory processing

**Risk Level:** 🟡 **MEDIUM** - Text processing logic, no external dependencies

---

#### 3. MarkdownFormatter (`markdown_formatter.py`)

**Methods Called:**
- `__init__()` - Constructor (no parameters)
- `format(data: Dict[str, Any], source_type: str, add_frontmatter: bool, source_file: str) -> str`

**Inputs:**
- `data`: Dictionary returned by `ContentCleaner.clean()`
- `source_type`: String, one of `"ppt"`, `"word"`, or `"generic"`
- `add_frontmatter`: Boolean, whether to include YAML frontmatter
- `source_file`: String, original filename (for metadata)

**Output Structure:**
```python
# Returns a single Markdown string

# With frontmatter (add_frontmatter=True):
"""---
title: "Document Title"
source: "filename.pdf"
source_type: PowerPoint
created: 2024-01-15
total_slides: 10
author: "John Doe"
tags:
  - powerpoint
  - imported
---

# Document Title

## Slide 1

### Slide Title

Content here...

#### Speaker Notes

> Notes content here

![image_slide_1_1](image_slide_1_1.png)

## Slide 2

...
"""

# Without frontmatter (add_frontmatter=False):
"""# Document Title

## Slide 1

...
"""
```

**Markdown Structure:**
- **PowerPoint**: Each slide becomes `## Slide N` with optional `### Title` and `#### Speaker Notes`
- **Word**: Continuous document with detected headings converted to `##`, `###`, etc.
- **Tables**: Formatted as GitHub-flavored Markdown tables
- **Images**: Placeholder references like `![image_name](image_name.png)`

**Filesystem Access:** ❌ NO - Pure in-memory string generation

**Risk Level:** 🟢 **LOW** - String formatting only, no external dependencies

---

#### 4. MarkdownCleanup (`markdown_cleanup.py`)

**Methods Called:**
- `__init__(remove_duplicate_lines: bool, standardize_headings: bool, fix_lists: bool, normalize_spacing: bool, add_metadata: bool, verbose: bool)`
- `cleanup_content(content: str) -> str`

**Inputs:**
- Constructor parameters (all boolean flags)
- `content`: Markdown string from `MarkdownFormatter.format()`

**Output Structure:**
```python
# Returns a cleaned Markdown string with:
# - Duplicate consecutive lines removed
# - Headings standardized (ATX style with proper spacing)
# - List formatting fixed (consistent bullet points)
# - Spacing normalized (max 2 blank lines)
# - Common issues fixed (emphasis, code blocks, links)
```

**Cleaning Operations:**
- Removes duplicate consecutive lines
- Converts underline-style headings to ATX (`#`)
- Standardizes bullet points to `-`
- Normalizes blank lines (max 2 consecutive)
- Fixes spacing around emphasis, code, links
- Ensures blank lines before/after code blocks and blockquotes

**Filesystem Access:** ❌ NO - Pure in-memory string processing

**Risk Level:** 🟢 **LOW** - String manipulation only, no external dependencies

---

### Risk Assessment Summary

| Module | Risk Level | Reason | Mitigation Strategy |
|--------|-----------|--------|---------------------|
| PDFExtractor | 🔴 HIGH | File I/O, PyMuPDF dependency, complex extraction logic | Mock with fixture data, test with sample PDFs |
| ContentCleaner | 🟡 MEDIUM | Complex regex patterns, text processing logic | Unit test with edge cases |
| MarkdownFormatter | 🟢 LOW | Pure string formatting | Simple unit tests |
| MarkdownCleanup | 🟢 LOW | Pure string manipulation | Simple unit tests |

**Highest Risk Module:** `PDFExtractor` - If it breaks, no content can be extracted.

---

## PART 2: DATA FLOW DIAGRAM

```
┌─────────────────┐
│   PDF File      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ PDFExtractor.extract(pdf_path, source_type)                 │
│                                                              │
│ Returns: extracted_data                                     │
│ {                                                            │
│   'type': 'powerpoint' | 'word',                            │
│   'slides': [...] | 'pages': [...],                         │
│   'total_pages': int,                                       │
│   'metadata': {...}                                         │
│ }                                                            │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ ContentCleaner.clean(extracted_data, source_type)           │
│                                                              │
│ Returns: cleaned_data (same structure, cleaned text)        │
│ {                                                            │
│   'type': 'powerpoint' | 'word',                            │
│   'slides': [                                               │
│     {                                                        │
│       'number': int,                                        │
│       'content': str,  ← CLEANED                            │
│       'notes': str,    ← CLEANED                            │
│       'images': [...], ← UNCHANGED                          │
│       'tables': [...]  ← CLEANED                            │
│     }                                                        │
│   ],                                                         │
│   'total_pages': int,                                       │
│   'metadata': {...}                                         │
│ }                                                            │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ MarkdownFormatter.format(cleaned_data, source_type,         │
│                          add_frontmatter, source_file)      │
│                                                              │
│ Returns: markdown (string)                                  │
│ """                                                          │
│ ---                                                          │
│ title: "..."                                                │
│ source: "..."                                               │
│ ---                                                          │
│                                                              │
│ # Title                                                      │
│                                                              │
│ ## Slide 1                                                   │
│ ...                                                          │
│ """                                                          │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ MarkdownCleanup.cleanup_content(markdown)                   │
│                                                              │
│ Returns: cleaned_markdown (string)                          │
│ - Duplicates removed                                        │
│ - Headings standardized                                     │
│ - Lists fixed                                               │
│ - Spacing normalized                                        │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Output File    │
│  (.md)          │
└─────────────────┘
```

---

## PART 3: MINIMUM VIABLE MOCKS

### Mock 1: PDFExtractor

```python
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
                        'images': [],
                        'tables': []
                    }
                ],
                'total_pages': 1,
                'metadata': {'Title': 'Test Document'}
            }
        else:  # word
            return {
                'type': 'word',
                'pages': [
                    {
                        'number': 1,
                        'content': 'Test Page Content',
                        'images': [],
                        'tables': []
                    }
                ],
                'total_pages': 1,
                'structure': {'headings': [], 'sections': []},
                'metadata': {'Title': 'Test Document'}
            }
```

### Mock 2: ContentCleaner

```python
class MockContentCleaner:
    """Minimum viable mock - passes through data unchanged"""
    
    def __init__(self):
        pass
    
    def clean(self, extracted_data: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """Return data unchanged (or with minimal cleaning)"""
        return extracted_data
```

### Mock 3: MarkdownFormatter

```python
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
```

### Mock 4: MarkdownCleanup

```python
class MockMarkdownCleanup:
    """Minimum viable mock - passes through content unchanged"""
    
    def __init__(self, **kwargs):
        # Accept any kwargs to match real constructor
        pass
    
    def cleanup_content(self, content: str) -> str:
        """Return content unchanged (or with minimal cleanup)"""
        # Minimal cleanup: just strip trailing whitespace
        return content.strip()
```

---

## PART 4: TESTING STRATEGY

### Unit Testing high_fidelity_pdf.py

```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import sys

# Mock the legacy imports before importing high_fidelity_pdf
sys.modules['pdf_extractor'] = Mock()
sys.modules['content_cleaner'] = Mock()
sys.modules['markdown_formatter'] = Mock()
sys.modules['markdown_cleanup'] = Mock()

# Now import and test
from high_fidelity_pdf import build_markdown

def test_build_markdown_ppt(tmp_path):
    """Test PowerPoint conversion with mocked legacy modules"""
    
    # Setup mocks
    mock_extractor = MockPDFExtractor()
    mock_cleaner = MockContentCleaner()
    mock_formatter = MockMarkdownFormatter()
    mock_cleanup = MockMarkdownCleanup()
    
    with patch('high_fidelity_pdf.PDFExtractor', return_value=mock_extractor), \
         patch('high_fidelity_pdf.ContentCleaner', return_value=mock_cleaner), \
         patch('high_fidelity_pdf.MarkdownFormatter', return_value=mock_formatter), \
         patch('high_fidelity_pdf.MarkdownCleanup', return_value=mock_cleanup):
        
        # Create test PDF
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")  # Minimal PDF header
        
        output_path = tmp_path / "output.md"
        
        # Run conversion
        result = build_markdown(pdf_path, output_path, "ppt", True)
        
        # Verify result structure
        assert result['status'] == 'completed'
        assert result['sourceType'] == 'ppt'
        assert result['pagesProcessed'] == 1
        assert output_path.exists()
```

### Integration Testing

For integration tests, use real legacy modules with small, controlled PDF fixtures:

```python
def test_integration_real_pdf(tmp_path):
    """Integration test with real legacy modules and a test PDF"""
    # Create a minimal real PDF using reportlab or similar
    # Test the full pipeline
    pass
```

---

## PART 5: REPLACEMENT CHECKLIST

If you need to replace any legacy module, ensure the replacement:

### PDFExtractor Replacement
- [ ] Returns dict with `type`, `slides`/`pages`, `total_pages`, `metadata` keys
- [ ] Each slide/page has `number`, `content`, `images`, `tables` keys
- [ ] Images have `index`, `page`, `bbox`, `width`, `height` keys
- [ ] Handles both PowerPoint and Word source types
- [ ] Returns empty dict `{}` on error (not None, not exception)

### ContentCleaner Replacement
- [ ] Accepts dict from PDFExtractor
- [ ] Returns same structure with cleaned text fields
- [ ] Preserves `images` and `metadata` unchanged
- [ ] Cleans `content`, `notes`, and `tables` fields
- [ ] Works in-memory (no file I/O)

### MarkdownFormatter Replacement
- [ ] Returns single Markdown string
- [ ] Supports `add_frontmatter` parameter
- [ ] Generates YAML frontmatter with `title`, `source`, `source_type`, `created`
- [ ] Formats slides as `## Slide N` headings
- [ ] Formats tables as GitHub-flavored Markdown
- [ ] Works in-memory (no file I/O)

### MarkdownCleanup Replacement
- [ ] Accepts Markdown string
- [ ] Returns cleaned Markdown string
- [ ] Supports constructor flags for cleanup options
- [ ] Preserves frontmatter structure
- [ ] Works in-memory (no file I/O)

---

## PART 6: DEPENDENCY GRAPH

```
high_fidelity_pdf.py
├── PDFExtractor (HIGH RISK)
│   └── Dependencies: fitz (PyMuPDF), PIL, loguru
│
├── ContentCleaner (MEDIUM RISK)
│   └── Dependencies: loguru
│
├── MarkdownFormatter (LOW RISK)
│   └── Dependencies: loguru
│
└── MarkdownCleanup (LOW RISK)
    └── Dependencies: click, loguru, yaml
```

**Critical Path:** PDFExtractor → ContentCleaner → MarkdownFormatter → MarkdownCleanup

**Bottleneck:** PDFExtractor (file I/O and PyMuPDF dependency)

---

## APPENDIX: Example Data Structures

### Example extracted_data (PowerPoint)

```python
{
    'type': 'powerpoint',
    'slides': [
        {
            'number': 1,
            'content': 'Introduction to AI\n\nKey Concepts:\n- Machine Learning\n- Deep Learning',
            'notes': 'Remember to emphasize the difference between ML and DL',
            'images': [
                {
                    'index': 1,
                    'page': 1,
                    'bbox': (100.0, 200.0, 400.0, 500.0),
                    'width': 300.0,
                    'height': 300.0
                }
            ],
            'tables': [
                [
                    ['Algorithm', 'Accuracy', 'Speed'],
                    ['Random Forest', '95%', 'Fast'],
                    ['Neural Network', '98%', 'Slow']
                ]
            ]
        }
    ],
    'total_pages': 1,
    'metadata': {
        'Title': 'AI Overview',
        'Author': 'John Doe',
        'Subject': 'Artificial Intelligence'
    }
}
```

### Example cleaned_data (after ContentCleaner)

```python
{
    'type': 'powerpoint',
    'slides': [
        {
            'number': 1,
            'content': 'Introduction to AI\n\nKey Concepts:\n- Machine Learning\n- Deep Learning',  # Cleaned
            'notes': 'Remember to emphasize the difference between ML and DL',  # Cleaned
            'images': [  # Unchanged
                {
                    'index': 1,
                    'page': 1,
                    'bbox': (100.0, 200.0, 400.0, 500.0),
                    'width': 300.0,
                    'height': 300.0
                }
            ],
            'tables': [  # Cells cleaned
                [
                    ['Algorithm', 'Accuracy', 'Speed'],
                    ['Random Forest', '95%', 'Fast'],
                    ['Neural Network', '98%', 'Slow']
                ]
            ]
        }
    ],
    'total_pages': 1,
    'metadata': {  # Unchanged
        'Title': 'AI Overview',
        'Author': 'John Doe',
        'Subject': 'Artificial Intelligence'
    }
}
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-04-25  
**Maintainer:** Bob (AI Assistant)