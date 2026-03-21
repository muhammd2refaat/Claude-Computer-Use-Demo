#!/bin/bash
set -e

# Start core desktop environment (Xvfb, tint2, mutter, x11vnc for the default display)
./start_all.sh

# Start noVNC proxy (for the default display on port 6080)
./novnc_startup.sh

# Ensure data directory exists for SQLite
sudo mkdir -p /data
sudo chown -R $USERNAME:$USERNAME /data

# Start the FastAPI backend
echo "🚀 Starting Computer Use API..."
python -m uvicorn computer_use_demo.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    > /tmp/api_stdout.log 2>&1 &

echo "✨ Computer Use API is ready!"
echo "➡️  Open http://localhost:8000 in your browser to begin"

# Keep the container running
tail -f /dev/null
