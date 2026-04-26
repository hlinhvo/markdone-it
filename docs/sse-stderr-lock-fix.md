# SSE Stderr Lock Fix

## Problem

When implementing SSE progress tracking, the application failed with the error:
```
Cannot collect output: 'stderr' is locked
```

This occurred during PDF and XLSX conversions when trying to process large files.

## Root Cause

The issue was caused by attempting to read from `proc.stderr` twice:

1. **First read**: Async streaming via `proc.stderr.getReader()` to capture progress events in real-time
2. **Second read**: Calling `proc.output()` which internally tries to read stderr again

In Deno, once a stream reader is acquired, the stream becomes "locked" and cannot be read again. The `proc.output()` method tries to read both stdout and stderr, causing the lock conflict.

## Solution

Instead of using `proc.output()`, we now:

1. **Manually collect stdout and stderr chunks** while streaming
2. **Stream both stdout and stderr** using separate readers
3. **Reconstruct the output** from collected chunks after the process completes

### Implementation Details

**Before (Broken):**
```typescript
const stderrReader = proc.stderr.getReader();
// ... stream stderr for progress ...

const output = await proc.output(); // ❌ Fails - stderr is locked
```

**After (Fixed):**
```typescript
// Collect both stdout and stderr
const stdoutChunks: Uint8Array[] = [];
const stderrChunks: Uint8Array[] = [];

// Stream stdout
const stdoutPromise = (async () => {
  const reader = proc.stdout.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    stdoutChunks.push(value);
  }
})();

// Stream stderr for progress updates
const stderrPromise = (async () => {
  const reader = proc.stderr.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    stderrChunks.push(value);
    // Parse progress events...
  }
})();

// Wait for completion
const [status] = await Promise.all([
  proc.status,
  stdoutPromise,
  stderrPromise,
]);

// Reconstruct output from chunks
const stdoutData = new Uint8Array(/* combine chunks */);
const stderrData = new Uint8Array(/* combine chunks */);
```

## Files Modified

1. **`markdone-universal/server.ts`**
   - `convertPdfToMarkdown()` function (lines 306-392)
   - `convertXlsxToMarkdown()` function (lines 467-558)

## Benefits

- ✅ **Fixes the stderr lock error** - No more conflicts when reading streams
- ✅ **Maintains SSE progress tracking** - Real-time updates still work
- ✅ **Preserves error handling** - stderr messages still captured for errors
- ✅ **No breaking changes** - API and behavior remain the same

## Testing

To verify the fix works:

1. Upload a large PDF (50+ pages) or XLSX file
2. Observe real-time progress updates in the UI
3. Verify conversion completes successfully
4. Check that error messages still display correctly if conversion fails

## Technical Notes

- The fix applies to both PDF and XLSX conversion functions
- Chunks are collected in arrays and reconstructed using `Uint8Array`
- Progress events are still parsed from stderr in real-time
- The process status is checked via `proc.status` instead of `output.success`