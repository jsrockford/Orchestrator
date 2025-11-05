#!/bin/bash
# Kill all gnome-terminal windows running npm run dev
pids=$(pgrep -f "npm run dev")

if [ -z "$pids" ]; then
    echo "No npm dev server found."
else
    echo "Killing npm dev server with PID(s): $pids"
    kill $pids
fi
