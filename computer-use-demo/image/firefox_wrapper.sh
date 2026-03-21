#!/bin/bash
# Firefox wrapper for concurrent session isolation.
# Each virtual display gets its own Firefox profile to prevent
# "Firefox is already running" errors when multiple sessions
# try to open Firefox simultaneously.

# Determine display number from DISPLAY env var (e.g., ":102" → "102")
DISPLAY_NUM="${DISPLAY#:}"
if [ -z "$DISPLAY_NUM" ]; then
    DISPLAY_NUM="1"
fi

# Create a unique profile directory for this display
PROFILE_DIR="$HOME/.mozilla/firefox/profile-display-${DISPLAY_NUM}"
mkdir -p "$PROFILE_DIR"

# Launch Firefox ESR with the isolated profile and --no-remote
# --no-remote prevents connecting to an existing Firefox instance
# --profile uses the display-specific profile directory
exec /usr/bin/firefox-esr --no-remote --profile "$PROFILE_DIR" "$@"
