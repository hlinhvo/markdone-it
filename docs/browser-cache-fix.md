# Browser Cache Fix Guide

## Problem
After rebuilding the container, the browser still shows old content ("Secure Artifacts Vault", "Purge Artifacts", missing "Download All" buttons).

## Root Cause
Browser is serving cached HTML/CSS/JS files instead of fetching the new versions from the server.

## Solutions (Try in Order)

### Solution 1: Hard Refresh (Recommended)
**Windows/Linux:**
- Chrome/Edge: `Ctrl + Shift + R` or `Ctrl + F5`
- Firefox: `Ctrl + Shift + R` or `Ctrl + F5`

**macOS:**
- Chrome/Edge: `Cmd + Shift + R`
- Firefox: `Cmd + Shift + R`
- Safari: `Cmd + Option + R`

### Solution 2: Clear Browser Cache
1. Open Developer Tools (`F12` or `Cmd/Ctrl + Shift + I`)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

### Solution 3: Incognito/Private Mode
Open the application in a new incognito/private window:
- Chrome/Edge: `Ctrl/Cmd + Shift + N`
- Firefox: `Ctrl/Cmd + Shift + P`
- Safari: `Cmd + Shift + N`

### Solution 4: Clear Site Data
1. Open Developer Tools (`F12`)
2. Go to "Application" tab (Chrome) or "Storage" tab (Firefox)
3. Click "Clear site data" or "Clear All"
4. Refresh the page

### Solution 5: Verify Container is Serving New Files
```bash
# Check if container is running with new image
podman ps

# Check container logs
podman logs markdone-universal

# Restart container
cd /Users/linhvh/IBM-Bob/MarkDone-v2/markdone-universal
./rebuild-and-restart.sh
```

## Expected Results After Fix
You should see:
- ✅ "📦 Download All" button in Processing Queue section
- ✅ "Completed Files" heading (not "Secure Artifacts Vault")
- ✅ "🗑 Delete All Files" button (not "Purge Artifacts")
- ✅ "📦 Download All" button in Completed Files section

## Verification
1. Open browser Developer Tools (`F12`)
2. Go to Network tab
3. Refresh page
4. Check if `index.html` shows status `200` (not `304 Not Modified`)
5. Click on `index.html` in Network tab
6. View Response tab - search for "Completed Files" - should be found
7. Search for "Secure Artifacts Vault" - should NOT be found