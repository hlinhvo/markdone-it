# Progress Emission Fix

## Problem

After fixing the stderr lock issue, progress events were still not appearing in the UI. The progress bar would show 0% and then jump directly to completion without showing intermediate progress updates.

## Root Cause

The Python scripts use a clever technique to protect stdout from library pollution:

```python
# Redirect stdout to stderr so only explicit JSON goes to real stdout
_real_stdout_fd = os.dup(sys.stdout.fileno())
_real_stdout = os.fdopen(_real_stdout_fd, "w")
sys.stdout = sys.stderr  # Everything else → stderr
```

However, the `emit_progress()` function was writing to `sys.stderr`:

```python
# BROKEN: This writes to the redirected stdout, not real stderr!
print(json.dumps(progress_data), file=sys.stderr, flush=True)
```

Since `sys.stdout` was redirected to `sys.stderr`, writing to `sys.stderr` was actually writing to the **redirected stdout**, which Deno wasn't capturing for progress events.

## Solution

We needed to preserve a reference to the **real stderr** file descriptor before any redirection:

```python
# Preserve both real stdout AND real stderr
_real_stdout_fd = os.dup(sys.stdout.fileno())
_real_stdout = os.fdopen(_real_stdout_fd, "w")
_real_stderr_fd = os.dup(sys.stderr.fileno())   # ← NEW
_real_stderr = os.fdopen(_real_stderr_fd, "w")   # ← NEW
sys.stdout = sys.stderr
```

Then update `emit_progress()` to write to the real stderr:

```python
def emit_progress(current: int, total: int, message: str = "") -> None:
    progress_data = {
        "type": "progress",
        "progress": int((current / total) * 100) if total > 0 else 0,
        "current": current,
        "total": total,
        "message": message or f"Processing page {current}/{total}"
    }
    # Write to REAL stderr, not redirected stdout
    _real_stderr.write(json.dumps(progress_data) + "\n")
    _real_stderr.flush()
```

## Files Modified

1. **[`markdone-universal/services/high_fidelity_pdf.py`](markdone-universal/services/high_fidelity_pdf.py)**
   - Lines 19-28: Added `_real_stderr` preservation
   - Lines 45-56: Updated `emit_progress()` to use `_real_stderr`

2. **[`markdone-universal/services/xlsx_converter.py`](markdone-universal/services/xlsx_converter.py)**
   - Lines 38-43: Added `_real_stderr` preservation
   - Lines 66-77: Updated `emit_progress()` to use `_real_stderr`

## Stream Flow Diagram

**Before (Broken):**
```
Python Process:
  stdout (fd 1) ──┐
                  ├──> sys.stderr ──> Deno stderr reader
  stderr (fd 2) ──┘                   (captures library noise + progress)
  
  emit_progress() writes to sys.stderr
  → Goes to redirected stdout
  → Mixed with library noise
  → Not properly parsed as JSON
```

**After (Fixed):**
```
Python Process:
  stdout (fd 1) ──> _real_stdout ──> Deno stdout reader (JSON result)
  stdout (fd 1) ──> sys.stderr   ──> (library noise only)
  stderr (fd 2) ──> _real_stderr ──> Deno stderr reader (progress JSON)
  
  emit_progress() writes to _real_stderr
  → Goes directly to real stderr
  → Captured by Deno's stderr reader
  → Properly parsed as JSON progress events
```

## Benefits

- ✅ **Real-time progress updates** - Progress events now properly stream to Deno
- ✅ **Clean separation** - stdout for final JSON, stderr for progress events
- ✅ **Library noise isolated** - Warnings/logs don't interfere with progress
- ✅ **Consistent behavior** - Both PDF and XLSX converters work the same way

## Testing

To verify the fix:

1. Upload a large PDF (50+ pages)
2. Observe the progress bar updating in real-time (e.g., 10%, 20%, 30%...)
3. See page numbers incrementing (e.g., "Processing page 5/50")
4. Verify smooth progress animation, not just 0% → 100%

The progress should now update continuously throughout the conversion process.