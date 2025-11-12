#!/bin/bash

# Navigate to the project root directory
cd /home/dgray/Projects/Orchestrator

# Activate the Python virtual environment
source venv/bin/activate

# Start the backend API server in the background
echo "Starting backend API server..."
python scripts/run_api_server.py --host 0.0.0.0 --port 9100 &

# Wait for 3 seconds to allow the backend to start
echo "Waiting for 3 seconds for backend to initialize..."
sleep 3

# Start the frontend development server
echo "Starting frontend development server..."
frontend/start-dev.sh
