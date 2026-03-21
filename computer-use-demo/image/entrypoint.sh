#!/bin/bash
set -e

# Start core desktop environment (Xvfb for the default display)
export DISPLAY=:${DISPLAY_NUM}

# Start Xvfb
./xvfb_startup.sh

# Start tint2 (non-fatal if it fails)
echo "starting tint2 on display :$DISPLAY_NUM ..."
tint2 -c $HOME/.config/tint2/tint2rc 2>/dev/null &
sleep 1

# Start mutter window manager (non-fatal if it fails)
echo "starting mutter..."
XDG_SESSION_TYPE=x11 mutter --replace --sm-disable 2>/dev/null &
sleep 1

# Start x11vnc for default display
./x11vnc_startup.sh

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
