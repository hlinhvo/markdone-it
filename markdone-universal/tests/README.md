# MarkDone Universal Test Suite

This directory contains the test suite for MarkDone Universal's Python sidecars.

## Test Files

- **`test_xlsx_converter.py`** - Comprehensive pytest suite for `xlsx_converter.py`
- **`integration.ts`** - Deno integration tests for the full server

## Running the xlsx_converter Tests

### Prerequisites

The tests require Python 3.11+ and the following packages:
- pytest
- openpyxl
- pandas

### Setup

#### Option 1: Using a Virtual Environment (Recommended)

```bash
# Create a virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements-dev.txt
```

#### Option 2: Using the Container

The tests can also be run inside the container where all dependencies are pre-installed:

```bash
# Build and run the container
./deploy.sh

# Execute tests in the container
podman exec -it markdone-universal python -m pytest tests/test_xlsx_converter.py -v
```

### Running Tests

```bash
# Run all tests with verbose output
python -m pytest tests/test_xlsx_converter.py -v

# Run specific test categories
python -m pytest tests/test_xlsx_converter.py -v -k "contract"
python -m pytest tests/test_xlsx_converter.py -v -k "markdown"
python -m pytest tests/test_xlsx_converter.py -v -k "json"
python -m pytest tests/test_xlsx_converter.py -v -k "compliance"
python -m pytest tests/test_xlsx_converter.py -v -k "error"
python -m pytest tests/test_xlsx_converter.py -v -k "edge"

# Run with coverage report
python -m pytest tests/test_xlsx_converter.py -v --cov=services --cov-report=html
```

## Test Coverage

The `test_xlsx_converter.py` suite covers:

### 1. Contract Tests
- ✅ Verify exact JSON payload fields for `vault_md` target
- ✅ Verify exact JSON payload fields for `vault_json` target
- ✅ Validate all required fields: status, outputPath, sourceType, sheetsProcessed, rowsProcessed, durationMs

### 2. Markdown Output Tests
- ✅ YAML frontmatter present when enabled
- ✅ YAML frontmatter absent when disabled
- ✅ `lang: en` field in frontmatter
- ✅ Sheet names become `##` headings
- ✅ Correct Markdown table structure (headers, separator, data rows)
- ✅ Multiple sheets all appear in output

### 3. JSON Output Tests
- ✅ Correct structure (source, sheets, columns, rows, row_count)
- ✅ `lang: en` field present
- ✅ Proper data serialization

### 4. Compliance Detection Tests
- ✅ Sheets with compliance keywords are flagged as compliance matrix
- ✅ Generic sheets are not flagged
- ✅ Detection works in both Markdown and JSON outputs

### 5. Error Handling Tests
- ✅ Missing input file → exit code 1, code: INPUT_NOT_FOUND
- ✅ Unsupported extension → exit code 1, code: UNSUPPORTED_FILE_TYPE
- ✅ Empty workbook → exit code 2, code: EXTRACTION_FAILED

### 6. Edge Cases
- ✅ Pipe characters `|` in cells are escaped as `\|`
- ✅ Cells over 500 characters are truncated with `…`
- ✅ Sheets over 2000 rows are capped
- ✅ Newlines in cells are replaced with spaces
- ✅ Empty cells are handled correctly
- ✅ `.xlsm` files are supported

## Test Design

All tests follow these principles:

1. **Self-contained**: Each test creates its own `.xlsx` fixture using `openpyxl`
2. **No external files**: All test data is generated programmatically
3. **Isolated**: Tests use pytest's `tmp_path` fixture for temporary files
4. **Contract-focused**: Tests verify the exact CLI contract that Deno depends on
5. **Comprehensive**: Cover success paths, error paths, and edge cases

## Adding New Tests

When adding new tests:

1. Use the `create_xlsx_fixture()` helper to create test workbooks
2. Use the `run_converter()` helper to execute the converter
3. Use the `parse_json_output()` helper to parse stdout
4. Follow the naming convention: `test_<category>_<specific_case>`
5. Add descriptive docstrings explaining what is being tested

Example:

```python
def test_new_feature(tmp_path: Path):
    """Verify that new feature works correctly."""
    xlsx_path = create_xlsx_fixture(
        tmp_path,
        "test.xlsx",
        {"Sheet1": [["Header"], ["Data"]]},
    )
    output_path = tmp_path / "output.md"
    
    exit_code, stdout, stderr = run_converter(xlsx_path, output_path)
    
    assert exit_code == 0
    # Add your assertions here
```

## Continuous Integration

These tests should be run:
- Before committing changes to `xlsx_converter.py`
- In CI/CD pipelines
- Before building new container images

## Troubleshooting

### Import errors
If you see `Import "pytest" could not be resolved`, ensure pytest is installed:
```bash
pip install pytest
```

### Module not found
If you see `No module named pytest`, ensure you're in the correct environment:
```bash
which python  # Should point to your venv or system Python with pytest installed
```

### Permission errors
Ensure the test has write access to the temporary directory (pytest handles this automatically).