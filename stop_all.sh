#!/bin/bash

# Navigate to the project root directory
cd /home/dgray/Projects/Orchestrator

echo "Stopping frontend development server..."
frontend/stop-dev.sh

echo "Stopping backend API server..."
backend/stop_backend.sh
