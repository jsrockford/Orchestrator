#!/bin/bash

SESSION_NAME="backend"

# Kill any existing backend session
tmux kill-session -t $SESSION_NAME 2>/dev/null

# Start a new detached tmux session
tmux new-session -d -s $SESSION_NAME

# Send the command to activate the venv and run the server
tmux send-keys -t $SESSION_NAME "source ../venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME "uvicorn server:app --host 0.0.0.0 --port 8000" C-m

echo "Backend server started in tmux session '$SESSION_NAME'"
