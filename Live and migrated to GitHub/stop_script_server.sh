#!/bin/bash
# Stop Script Runner Server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/script_server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No PID file found. Server may not be running."
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    kill "$PID"
    rm "$PID_FILE"
    echo "✅ Script Runner Server stopped (PID: $PID)"
else
    echo "⚠️  Process $PID not found. Cleaning up PID file."
    rm "$PID_FILE"
fi

