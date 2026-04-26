# Download All Feature - Quick Reference Guide

## 📋 Summary

This feature adds bulk download functionality and improves UI terminology in MarkDone Universal.

### Key Changes
1. ✅ **Download All as ZIP** - Bulk download for completed files
2. ✅ **Fix Long Filenames** - Proper text overflow handling
3. ✅ **Better Terminology** - User-friendly section names

---

## 🎯 Implementation Checklist

### Backend (server.ts)

- [ ] Add JSZip or equivalent library import
- [ ] Create `createZipArchive()` utility function
- [ ] Add `GET /api/download-queue-zip` endpoint
- [ ] Add `GET /api/download-history-zip` endpoint
- [ ] Add timestamp generation for ZIP filenames
- [ ] Add error handling for missing files
- [ ] Test ZIP creation with multiple files

### Frontend HTML (index.html)

- [ ] Change "Secure Artifacts Vault" → "Completed Files"
- [ ] Change "Purge Artifacts" → "Delete All Files"
- [ ] Update section icon (🛡️ → 📁)
- [ ] Update section description
- [ ] Add ZIP download button to Processing Queue
- [ ] Add ZIP download button to Completed Files section
- [ ] Add CSS for filename overflow handling

### Frontend JavaScript (app.js)

- [ ] Create `downloadQueueZip()` function
- [ ] Create `downloadHistoryZip()` function
- [ ] Wire up event listeners for ZIP buttons
- [ ] Update button states (enable/disable)
- [ ] Add file count to button text
- [ ] Add loading state during ZIP creation
- [ ] Add success/error feedback messages

### Testing

- [ ] Test with 1 file
- [ ] Test with 5-10 files
- [ ] Test with 0 files (error handling)
- [ ] Test with long filenames
- [ ] Test filename overflow in tables
- [ ] Test on Chrome, Firefox, Safari
- [ ] Test on mobile devices

---

## 💻 Code Snippets

### Backend: ZIP Creation Function

```typescript
import { JSZip } from "https://deno.land/x/jszip@0.11.0/mod.ts";

async function createZipArchive(
  files: Array<{ path: string; name: string }>
): Promise<Uint8Array> {
  const zip = new JSZip();
  
  for (const file of files) {
    try {
      const content = await Deno.readFile(file.path);
      zip.file(file.name, content);
    } catch (error) {
      console.error(`Failed to add ${file.name} to ZIP:`, error);
    }
  }
  
  return await zip.generateAsync({ type: "uint8array" });
}

function getTimestampedZipName(prefix: string = "markdone-exports"): string {
  const now = new Date();
  const timestamp = now.toISOString()
    .replace(/[:.]/g, "-")
    .replace("T", "-")
    .slice(0, 19);
  return `${prefix}-${timestamp}.zip`;
}
```

### Backend: ZIP Download Endpoint

```typescript
router.get("/api/download-queue-zip", async (ctx) => {
  try {
    // Get completed files from queue (stored in memory or session)
    const completedFiles = getCompletedQueueFiles(); // Implement this
    
    if (completedFiles.length === 0) {
      ctx.response.status = 404;
      ctx.response.body = { message: "No completed files available" };
      return;
    }
    
    const zipBuffer = await createZipArchive(completedFiles);
    const filename = getTimestampedZipName("markdone-queue");
    
    ctx.response.headers.set("Content-Type", "application/zip");
    ctx.response.headers.set(
      "Content-Disposition",
      `attachment; filename="${filename}"`
    );
    ctx.response.body = zipBuffer;
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { message: "Failed to create ZIP archive" };
  }
});

router.get("/api/download-history-zip", async (ctx) => {
  try {
    const outputDir = config.vaultOutputDir;
    const files: Array<{ path: string; name: string }> = [];
    
    for await (const entry of Deno.readDir(outputDir)) {
      if (entry.isFile) {
        files.push({
          path: `${outputDir}/${entry.name}`,
          name: entry.name,
        });
      }
    }
    
    if (files.length === 0) {
      ctx.response.status = 404;
      ctx.response.body = { message: "No files in history" };
      return;
    }
    
    const zipBuffer = await createZipArchive(files);
    const filename = getTimestampedZipName("markdone-history");
    
    ctx.response.headers.set("Content-Type", "application/zip");
    ctx.response.headers.set(
      "Content-Disposition",
      `attachment; filename="${filename}"`
    );
    ctx.response.body = zipBuffer;
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { message: "Failed to create ZIP archive" };
  }
});
```

### Frontend: HTML Changes

```html
<!-- Processing Queue Section - Add ZIP button -->
<div class="action-bar">
  <button id="convert-button" class="btn btn-primary">Process Queue</button>
  <button id="clear-button" class="btn btn-secondary">Purge Staging</button>
  <button id="download-queue-zip-button" class="btn btn-secondary">
    📦 Download All as ZIP
  </button>
</div>

<!-- Completed Files Section - Update titles and buttons -->
<div class="glass-card output-section">
  <div class="section-header">
    <div class="section-icon">📁</div>
    <h2 class="section-heading">Completed Files</h2>
  </div>
  <p class="section-desc">Successfully converted files ready for download.</p>
  
  <!-- ... table ... -->
  
  <div class="action-bar" style="margin-top: 20px;">
    <button id="download-history-zip-button" class="btn btn-secondary">
      📦 Download All as ZIP
    </button>
    <button id="clear-history-button" class="btn-danger-ghost">
      🗑 Delete All Files
    </button>
  </div>
</div>
```

### Frontend: CSS for Overflow

```css
/* Fix long filename overflow */
tbody td {
  padding: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  color: var(--text-main);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Allow wrapping for Name column */
tbody td:first-child {
  max-width: 250px;
  word-break: break-word;
  white-space: normal;
}

/* Tooltip for full filename on hover */
tbody td:first-child:hover {
  overflow: visible;
  white-space: normal;
  position: relative;
  z-index: 10;
}
```

### Frontend: JavaScript Functions

```javascript
async function downloadQueueZip() {
  const completedFiles = queue.filter(item => item.status === "completed");
  
  if (completedFiles.length === 0) {
    feedback = "No completed files to download.";
    updateDOM();
    return;
  }
  
  // Smart download: single file downloads directly, multiple files as ZIP
  if (completedFiles.length === 1) {
    const file = completedFiles[0];
    if (file.downloadUrl) {
      const a = document.createElement("a");
      a.href = file.downloadUrl;
      a.download = file.outputName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      feedback = "File downloaded.";
      updateDOM();
      return;
    }
  }
  
  try {
    feedback = "Creating ZIP archive...";
    updateDOM();
    
    const response = await fetch("/api/download-queue-zip");
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || "Failed to create ZIP");
    }
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    
    // Extract filename from Content-Disposition header
    const disposition = response.headers.get("Content-Disposition");
    const filenameMatch = disposition?.match(/filename="(.+)"/);
    a.download = filenameMatch?.[1] || "markdone-exports.zip";
    
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    feedback = `Downloaded ${completedFiles.length} file(s) as ZIP.`;
  } catch (error) {
    feedback = error.message || "Failed to download ZIP archive.";
  }
  updateDOM();
}

async function downloadHistoryZip() {
  try {
    feedback = "Creating ZIP archive...";
    updateDOM();
    
    const response = await fetch("/api/download-history-zip");
    
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.message || "Failed to create ZIP");
    }
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    
    const disposition = response.headers.get("Content-Disposition");
    const filenameMatch = disposition?.match(/filename="(.+)"/);
    a.download = filenameMatch?.[1] || "markdone-history.zip";
    
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    feedback = "History downloaded as ZIP.";
  } catch (error) {
    feedback = error.message || "Failed to download ZIP archive.";
  }
  updateDOM();
}

// Update button states with smart text
function updateDOM() {
  // ... existing code ...
  
  const queueZipBtn = document.getElementById("download-queue-zip-button");
  const completedCount = queue.filter(item => item.status === "completed").length;
  
  if (queueZipBtn) {
    queueZipBtn.disabled = completedCount === 0;
    
    // Smart button text based on file count
    if (completedCount === 0) {
      queueZipBtn.textContent = "📦 Download All";
    } else if (completedCount === 1) {
      queueZipBtn.textContent = "⬇ Download File";
    } else {
      queueZipBtn.textContent = `📦 Download All as ZIP (${completedCount})`;
    }
  }
}

// Wire up event listeners
function wireDom() {
  // ... existing code ...
  
  const downloadQueueZipButton = document.getElementById("download-queue-zip-button");
  const downloadHistoryZipButton = document.getElementById("download-history-zip-button");
  
  if (downloadQueueZipButton) {
    downloadQueueZipButton.addEventListener("click", downloadQueueZip);
  }
  
  if (downloadHistoryZipButton) {
    downloadHistoryZipButton.addEventListener("click", downloadHistoryZip);
  }
}
```

---

## 🧪 Testing Commands

```bash
# Start development server
cd markdone-universal
deno task dev

# Test with sample files
curl -X POST http://localhost:8000/api/convert \
  -F "files=@test1.pdf" \
  -F "files=@test2.pdf" \
  -F "target=vault_md"

# Test ZIP download
curl -O -J http://localhost:8000/api/download-queue-zip
curl -O -J http://localhost:8000/api/download-history-zip

# Verify ZIP contents
unzip -l markdone-exports-*.zip
```

---

## 📝 User Stories

### Story 1: Bulk Download from Queue
**As a** user  
**I want to** download all completed conversions as a single ZIP file  
**So that** I don't have to click download for each file individually

**Acceptance Criteria:**
- ✅ Button appears in Processing Queue section
- ✅ Button is disabled when no completed files exist
- ✅ Button shows count of files: "Download All as ZIP (5)"
- ✅ Clicking button downloads ZIP with timestamp
- ✅ ZIP contains only successfully completed files
- ✅ User sees feedback message during and after download

### Story 2: Bulk Download from History
**As a** user  
**I want to** download all files from my conversion history  
**So that** I can backup or share multiple converted files at once

**Acceptance Criteria:**
- ✅ Button appears in Completed Files section
- ✅ Button is disabled when history is empty
- ✅ Clicking button downloads ZIP with all history files
- ✅ ZIP filename includes timestamp
- ✅ User sees feedback message

### Story 3: Long Filename Display
**As a** user  
**I want to** see long filenames properly displayed in tables  
**So that** the layout doesn't break and I can still read the names

**Acceptance Criteria:**
- ✅ Long filenames are truncated with ellipsis (...)
- ✅ Hovering shows full filename
- ✅ Table layout remains intact
- ✅ Works on mobile devices

### Story 4: Clear Terminology
**As a** user  
**I want to** see clear, understandable section names  
**So that** I know what each section does without technical jargon

**Acceptance Criteria:**
- ✅ "Secure Artifacts Vault" renamed to "Completed Files"
- ✅ "Purge Artifacts" renamed to "Delete All Files"
- ✅ Section icon updated to 📁
- ✅ Description text is clear and user-friendly

---

## 🚀 Deployment Steps

1. **Backup current version**
   ```bash
   git commit -am "Backup before download-all feature"
   git tag v1.0-pre-download-all
   ```

2. **Implement changes**
   - Update server.ts
   - Update index.html
   - Update app.js

3. **Test locally**
   ```bash
   deno task dev
   # Test all scenarios
   ```

4. **Build and deploy**
   ```bash
   ./rebuild-and-restart.sh
   ```

5. **Verify in production**
   - Test ZIP downloads
   - Check UI updates
   - Verify filename overflow handling

---

## 🐛 Troubleshooting

### Issue: ZIP download fails
**Solution:** Check server logs, verify file permissions, ensure files exist

### Issue: Button stays disabled
**Solution:** Check if files are marked as "completed" status, verify updateDOM() is called

### Issue: Long filenames still break layout
**Solution:** Verify CSS is applied, check browser dev tools, clear cache

### Issue: ZIP file is empty
**Solution:** Verify file paths are correct, check createZipArchive() function

---

## 📚 References

- [JSZip Documentation](https://stuk.github.io/jszip/)
- [Deno File System API](https://deno.land/api@v1.40.0?s=Deno.readFile)
- [MDN: Blob API](https://developer.mozilla.org/en-US/docs/Web/API/Blob)
- [MDN: Download Attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/a#attr-download)

---

**Last Updated:** 2026-04-26  
**Version:** 1.0  
**Status:** Ready for Implementation