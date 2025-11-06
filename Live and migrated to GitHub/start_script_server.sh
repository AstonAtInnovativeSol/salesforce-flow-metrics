#!/bin/bash
# Start Script Runner Server in Background
# This allows you to use your terminal for other commands while the server runs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/script_server.pid"
LOG_FILE="$SCRIPT_DIR/script_server.log"

# Check if server is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️  Script server is already running (PID: $OLD_PID)"
        echo "   Use './stop_script_server.sh' to stop it first"
        exit 1
    else
        # Clean up stale PID file
        rm "$PID_FILE"
    fi
fi

# Start the server in background
cd "$SCRIPT_DIR"
nohup python3 script_runner_server.py > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# Save PID
echo $SERVER_PID > "$PID_FILE"

echo "✅ Script Runner Server started!"
echo "   PID: $SERVER_PID"
echo "   URL: http://localhost:5000"
echo "   Log: $LOG_FILE"
echo ""
echo "To stop the server, run: ./stop_script_server.sh"
echo "To view logs: tail -f $LOG_FILE"

