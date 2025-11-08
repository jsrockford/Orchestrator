#!/bin/bash
PID_FILE="/home/dgray/Projects/Orchestrator/backend/backend.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null; then
        echo "Stopping backend server with PID $PID..."
        kill $PID
        # Wait a moment for the process to terminate
        sleep 1
        if ps -p $PID > /dev/null; then
            echo "Process $PID did not stop gracefully, forcing..."
            kill -9 $PID
        fi
        rm "$PID_FILE"
        echo "Backend server stopped."
    else
        echo "Backend server not running (stale PID file found)."
        rm "$PID_FILE"
    fi
else
    echo "Backend server not running (no PID file found)."
fi
