#!/bin/bash

# Navigate to the project root directory
cd /home/dgray/Projects/Orchestrator

echo "=========================================="
echo "Starting Orchestrator Services"
echo "=========================================="

# Activate the Python virtual environment
source venv/bin/activate

# Start the backend API server in the background
echo "Starting backend API server on port 9100..."
python scripts/run_api_server.py --host 0.0.0.0 --port 9100 &
backend_pid=$!
echo $backend_pid > backend/backend.pid
echo "Backend PID: $backend_pid"

# Wait for backend to initialize
echo "Waiting 3 seconds for backend to initialize..."
sleep 3

# Verify backend is running
if kill -0 $backend_pid 2>/dev/null; then
    echo "✓ Backend API server started successfully"
else
    echo "✗ Backend API server failed to start!"
    exit 1
fi

# Start the frontend development server in a new gnome-terminal
echo "Starting frontend development server on port 9101..."
gnome-terminal -- bash -c "cd /home/dgray/Projects/Orchestrator/frontend && npm run dev -- --host"

echo ""
echo "=========================================="
echo "All services started successfully"
echo "=========================================="
echo ""
echo "Backend:  http://localhost:9100"
echo "Frontend: http://localhost:9101"
