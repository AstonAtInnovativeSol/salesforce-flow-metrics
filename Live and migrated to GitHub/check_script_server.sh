#!/bin/bash
# Check Script Runner Server Status

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/script_server.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ Script Runner Server is NOT running"
    echo "   Start it with: ./start_script_server.sh"
    exit 1
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ Script Runner Server is running"
    echo "   PID: $PID"
    echo "   URL: http://localhost:5000"
    echo ""
    echo "To stop: ./stop_script_server.sh"
    echo "To view logs: tail -f $SCRIPT_DIR/script_server.log"
else
    echo "❌ Script Runner Server is NOT running (stale PID file)"
    rm "$PID_FILE"
    echo "   Start it with: ./start_script_server.sh"
fi

