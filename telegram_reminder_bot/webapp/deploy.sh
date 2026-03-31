#!/bin/bash
# Deploy script for Calendar Web App with Cloudflare Tunnel

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "📦 Installing dependencies..."
npm install

echo "🔨 Building React app..."
npm run build

echo "✅ Build complete!"
echo ""
echo "📁 Built files are in: $SCRIPT_DIR/dist"
echo ""
echo "To start the server:"
echo "  ../venv/bin/python server.py"
echo ""
echo "Then in another terminal, start Cloudflare Tunnel:"
echo "  cloudflared tunnel --url http://localhost:3000"
echo ""
echo "Copy the HTTPS URL and add to your bot's .env:"
echo "  WEBAPP_URL=https://xxx.trycloudflare.com"
