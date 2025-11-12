# TMUX Testing Overview

## Step-by-Step Instructions

### Claude Session

1. Open a terminal window.
2. Start Claude in a new tmux session:
   ```bash
   tmux new -s claude
   safe_claude --dangerously-skip-permissions
   ```
3. Accept the bypass warning if prompted.
4. Detach from tmux (`Ctrl+b`, `d`) so the session keeps running in the background.

### Gemini Session

1. Open a second terminal window.
2. Start Gemini in another tmux session:
   ```bash
   tmux new -s gemini
   safe_gemini --yolo
   ```
3. Wait until the prompt is ready.
4. Detach from tmux (`Ctrl+b`, `d`) to release the session.

### Orchestrator Run

1. Open a third terminal window.
2. From the repo root, run the orchestrated discussion:
   ```bash
   python3 -m examples.run_orchestrated_discussion "Evaluate next release" \
     --claude-session claude \
     --gemini-session gemini \
     --log-file logs/discussion-manual.log
   ```
3. If you need longer start-up buffers, add `--gemini-startup-timeout` or `--gemini-init-wait`.

### Useful Tips

- To verify no manual clients are attached before running the orchestrator:
  ```bash
  tmux list-clients -t claude
  tmux list-clients -t gemini
  ```
- View the conversation log afterwards: `cat logs/discussion-manual.log`
- Kill sessions when finished:
  ```bash
  tmux kill-session -t claude
  tmux kill-session -t gemini
  ```
