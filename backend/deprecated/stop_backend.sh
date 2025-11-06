#!/bin/bash

SESSION_NAME="backend"

tmux kill-session -t $SESSION_NAME 2>/dev/null

echo "Backend server session '$SESSION_NAME' terminated."
