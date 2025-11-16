#!/bin/bash
PID_FILE="/home/dgray/Projects/Orchestrator/backend/backend.pid"
LOG_FILE="/home/dgray/Projects/Orchestrator/backend/logs/backend.log"

# Ensure log directory exists
mkdir -p /home/dgray/Projects/Orchestrator/backend/logs

echo "Starting backend server..."
cd /home/dgray/Projects/Orchestrator

# Activate virtual environment
source venv/bin/activate

# Start the server in the background
nohup python scripts/run_api_server.py --host 0.0.0.0 --port 9100 > "$LOG_FILE" 2>&1 &

# Store the PID
echo $! > "$PID_FILE"

echo "Backend server started with PID $(cat $PID_FILE). Output is logged to $LOG_FILE"
