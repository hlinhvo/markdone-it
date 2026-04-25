#!/bin/bash
# Quick rebuild and restart script for MarkDone Universal

echo "🔨 Rebuilding container with updated static files..."
podman build -t markdone-universal:latest -f Containerfile .

echo "🛑 Stopping existing container (if running)..."
podman stop markdone-universal 2>/dev/null || true
podman rm markdone-universal 2>/dev/null || true

echo "🚀 Starting new container..."
podman run -d \
  --name markdone-universal \
  -p 7482:7482 \
  -v "$(pwd)/outputs:/app/outputs:Z" \
  markdone-universal:latest

echo "✅ Container rebuilt and restarted!"
echo "📍 Access the app at: http://localhost:7482"
echo ""
echo "To view logs: podman logs -f markdone-universal"

# Made with Bob
