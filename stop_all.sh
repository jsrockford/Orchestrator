#!/bin/bash

# Navigate to the project root directory
cd /home/dgray/Projects/Orchestrator

echo "=========================================="
echo "Stopping Orchestrator Services"
echo "=========================================="

# Kill frontend (npm dev server)
echo "Stopping frontend development server..."
pids=$(pgrep -f "npm run dev")
if [ -n "$pids" ]; then
    echo "Killing npm dev server (PID: $pids)"
    kill $pids 2>/dev/null
    sleep 1
    # Force kill if still running
    pkill -9 -f "npm run dev" 2>/dev/null || true
else
    echo "No npm dev server found"
fi

# Kill backend (Python API server)
echo "Stopping backend API server..."
pids=$(pgrep -f "run_api_server.py")
if [ -n "$pids" ]; then
    echo "Killing Python API servers (PIDs: $pids)"
    kill $pids 2>/dev/null
    sleep 1
    # Force kill if still running
    pkill -9 -f "run_api_server.py" 2>/dev/null || true
else
    echo "No Python API server found"
fi

# Kill tmux sessions (Claude, Gemini, Codex, Qwen CLI sessions)
echo "Stopping tmux sessions..."
for session in claude gemini codex qwen; do
    if tmux has-session -t "$session" 2>/dev/null; then
        echo "Killing tmux session: $session"
        tmux kill-session -t "$session" 2>/dev/null || true
    fi
done

# Final verification - kill any stragglers
echo "Verifying all processes are stopped..."
sleep 1

remaining_npm=$(pgrep -f "npm run dev" | wc -l)
remaining_api=$(pgrep -f "run_api_server.py" | wc -l)

if [ "$remaining_npm" -gt 0 ]; then
    echo "Warning: $remaining_npm npm process(es) still running, force killing..."
    pkill -9 -f "npm run dev" 2>/dev/null || true
fi

if [ "$remaining_api" -gt 0 ]; then
    echo "Warning: $remaining_api Python API process(es) still running, force killing..."
    pkill -9 -f "run_api_server.py" 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "All services stopped successfully"
echo "=========================================="
