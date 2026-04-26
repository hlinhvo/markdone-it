# CI/CD Pipeline Setup

## Overview

MarkDone v2 now includes a comprehensive GitHub Actions CI/CD pipeline that automatically runs tests on every push and pull request.

## Workflow File

**Location:** `.github/workflows/ci.yml`

## Pipeline Jobs

### 1. Python Tests (`test-python`)
- **Runs on:** Ubuntu Latest
- **Python Version:** 3.11
- **Purpose:** Execute pytest test suite for Python sidecars
- **Steps:**
  1. Checkout code
  2. Set up Python 3.11 with pip caching
  3. Install dependencies from `requirements-dev.txt`
  4. Run `pytest tests/ -v --tb=short`
  5. Upload test results as artifacts

### 2. Deno Tests (`test-deno`)
- **Runs on:** Ubuntu Latest
- **Deno Version:** 2.x
- **Purpose:** Execute Deno integration tests
- **Steps:**
  1. Checkout code
  2. Set up Deno 2.x
  3. Run integration tests with required permissions

### 3. Code Quality (`lint`)
- **Runs on:** Ubuntu Latest
- **Purpose:** Run linting tools for code quality
- **Tools:**
  - `ruff` for Python linting
  - `mypy` for Python type checking
  - `deno lint` for TypeScript linting
- **Note:** Linting failures are non-blocking (|| true)

## Triggers

The pipeline runs on:
- **Push** to `main` or `develop` branches
- **Pull requests** targeting `main` or `develop` branches

## Test Coverage

The pipeline validates:
- ✅ PDF conversion functionality (`test_pdf_sidecar.py`)
- ✅ XLSX conversion functionality (`test_xlsx_converter.py`)
- ✅ Deno server integration (`integration.ts`)
- ✅ Code quality and style compliance

## Artifacts

Test results are uploaded as artifacts and available for download from the GitHub Actions UI:
- `pytest-results` - Contains pytest XML reports (if generated)

## Local Testing

To run the same tests locally:

```bash
# Python tests
cd markdone-universal
python -m pytest tests/ -v

# Deno tests
cd markdone-universal
deno test --allow-net --allow-read --allow-write --allow-env tests/integration.ts

# Linting
ruff check services/ tests/
deno lint server.ts
```

## Benefits

1. **Automated Quality Assurance** - Every code change is automatically tested
2. **Early Bug Detection** - Issues are caught before merging
3. **Consistent Testing** - Same environment for all contributors
4. **Documentation** - Test results provide living documentation
5. **Confidence** - Green builds indicate production-ready code

## Future Enhancements

Potential improvements for the CI/CD pipeline:
- Add code coverage reporting with codecov
- Add security scanning with Snyk or Dependabot
- Add performance benchmarking
- Add container image building and publishing
- Add deployment automation for staging/production

## Related Documentation

- [`markdone-universal/tests/README.md`](../markdone-universal/tests/README.md) - Test suite documentation
- [`markdone-universal/tests/TEST_SUITE_SUMMARY.md`](../markdone-universal/tests/TEST_SUITE_SUMMARY.md) - Test coverage summary
- [`markdone-universal/tests/TEST_REPORT.md`](../markdone-universal/tests/TEST_REPORT.md) - Detailed test results