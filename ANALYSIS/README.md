# Communication Workflow Analysis

**Comprehensive documentation of the Orchestrator's input/output handling system**

---

## 📚 Document Overview

This analysis covers the complete communication flow from the orchestrator through tmux controllers to AI CLI sessions. Choose the document that matches your needs:

### 1. **COMMUNICATION_WORKFLOW.md** - Main Architecture Guide
**Best for**: Understanding the overall system design and data flow

**Covers**:
- End-to-end request-response cycle
- How the orchestrator dispatches commands
- Input transmission via tmux
- Output capture and response handling
- Automation pause/resume mechanics
- Sequence diagrams and timing information
- Status reporting and introspection

**Key sections**:
- Section 1: Overview and architecture
- Section 2: Input flow (sending prompts)
- Section 3: Output flow (receiving responses)
- Section 4: Response cycle in ConversationManager
- Section 5: Automation pause & resume
- Section 6: Status reporting
- Section 7-9: Timing, error handling, and sequences

**Read this first** if you're new to the orchestrator or want a complete picture.

---

### 2. **TMUX_IO_MECHANICS.md** - Technical Deep Dive
**Best for**: Understanding the low-level tmux operations and I/O handling

**Covers**:
- Tmux pane architecture and text flow
- The `send-keys` command and literal mode
- The `capture-pane` command for output
- Output delta calculation (detecting new lines)
- Waiting for response completion
- Manual client detection for pause handling
- ANSI escape code removal and UI cleaning
- Response delimiters and health checks
- Performance characteristics

**Key sections**:
- Section 1-2: Tmux fundamentals
- Section 3-4: Input transmission and output capture
- Section 5: Waiting for responses
- Section 6: Manual attach detection
- Section 7-8: Queuing and keystroke handling
- Section 9-12: Output cleaning, performance, debugging

**Read this** if you need to troubleshoot low-level I/O issues or optimize performance.

---

### 3. **TROUBLESHOOTING_GUIDE.md** - Practical Reference
**Best for**: Diagnosing specific problems and fixing issues

**Covers**:
- Symptom decoder (command hangs, no response, etc.)
- Log analysis patterns
- Step-by-step tracing procedures
- Common configuration issues
- Recovery procedures
- Performance tuning
- Testing & validation
- Emergency procedures

**Key sections**:
- Section 1: Symptom decoder with fixes
- Section 2: Log analysis patterns
- Section 3: Tracing a single command
- Section 4: Configuration issues
- Section 5-8: Recovery, tuning, testing, emergency procedures
- Quick reference card

**Read this** when something isn't working and you need practical solutions.

---

## 🔄 Recommended Reading Order

### For New Team Members:
1. **COMMUNICATION_WORKFLOW.md** (Sections 1-4)
2. **TMUX_IO_MECHANICS.md** (Sections 1-4)
3. **TROUBLESHOOTING_GUIDE.md** (Sections 1-2)

### For Debugging Issues:
1. **TROUBLESHOOTING_GUIDE.md** (Section 1 - Symptom decoder)
2. **COMMUNICATION_WORKFLOW.md** (Section 3 - Output flow)
3. **TMUX_IO_MECHANICS.md** (Section 5-6 - Specific issue area)

### For Performance Optimization:
1. **TMUX_IO_MECHANICS.md** (Section 12 - Performance)
2. **COMMUNICATION_WORKFLOW.md** (Section 7 - Timings)
3. **TROUBLESHOOTING_GUIDE.md** (Section 6 - Performance tuning)

### For Configuration Changes:
1. **COMMUNICATION_WORKFLOW.md** (Section 7 - Timing & delays)
2. **TMUX_IO_MECHANICS.md** (Section 5 - Ready indicators)
3. **TROUBLESHOOTING_GUIDE.md** (Section 4 - Configuration issues)

---

## 🎯 Quick Start: Core Concepts

### The Basic Flow

```
User Code
    ↓
ConversationManager.facilitate_discussion()
    ├─ Build prompt for next speaker
    │
    ├─ Orchestrator.dispatch_command(prompt)
    │   └─ Check if automation paused (manual client attached?)
    │   ├─ If paused: Queue command
    │   └─ If active: TmuxController.send_command()
    │       ├─ Send text via tmux send-keys -l (literal mode)
    │       ├─ Send Enter key to submit
    │       └─ Return success/failure
    │
    ├─ Read response: TmuxController.get_last_output()
    │   └─ Calculate delta (new lines since before sending)
    │
    ├─ Parse response: OutputParser.split_prompt_and_response()
    │   └─ Extract AI's response from pane output
    │
    ├─ Validate response: OutputParser.validate_response()
    │   └─ Check for errors, minimum length, etc.
    │
    ├─ If invalid: Retry (configurable max_retries)
    ├─ If queued: Wait for automation resume
    │
    └─ Record turn in conversation history
```

### Key System Properties

1. **Sequential**: One command at a time, never parallel
2. **Automation-aware**: Pauses when human attaches to tmux
3. **Queue-safe**: Commands queued and replayed in order
4. **Delta-based**: Only new output is captured per command
5. **Retry-capable**: Invalid responses are retried with backoff

---

## 📖 Documentation Map

```
README.md (this file)
├── COMMUNICATION_WORKFLOW.md
│   ├── 1. Overview: Architecture
│   ├── 2. Input Flow: Sending Prompts
│   ├── 3. Output Flow: Receiving Responses
│   ├── 4. Response Cycle in ConversationManager
│   ├── 5. Automation Pause & Resume
│   ├── 6. Status Reporting
│   ├── 7-10. Timing, Error Handling, Sequences, Q&A
│   └── 11-12. Testing & Benefits
│
├── TMUX_IO_MECHANICS.md
│   ├── 1. Tmux Pane Architecture
│   ├── 2. Sending Input: send-keys
│   ├── 3. Capturing Output: capture-pane
│   ├── 4. Output Delta Calculation
│   ├── 5. Waiting for Responses
│   ├── 6. Manual Client Detection
│   ├── 7. Send vs Queue Logic
│   ├── 8. Keystroke Handling
│   ├── 9. Output Cleaning
│   ├── 10. Response Delimiters
│   ├── 11. Health Checks
│   ├── 12. Performance & Debugging
│   └── 13. Summary
│
└── TROUBLESHOOTING_GUIDE.md
    ├── 1. Symptom Decoder
    │   ├── Command hangs / No response
    │   ├── Response empty
    │   └── Commands queued / Not executing
    │
    ├── 2. Log Analysis Patterns
    ├── 3. Tracing a Single Command
    ├── 4. Configuration Issues
    ├── 5. Recovery Procedures
    ├── 6. Performance Tuning
    ├── 7. Testing & Validation
    ├── 8. Emergency Procedures
    ├── 9. Glossary
    └── Quick Reference Card
```

---

## 🔍 How to Find What You Need

### "How does the orchestrator send a prompt?"
→ **COMMUNICATION_WORKFLOW.md**, Section 2.1-2.3

### "How is output captured from tmux?"
→ **TMUX_IO_MECHANICS.md**, Section 3

### "Why is my command not executing?"
→ **TROUBLESHOOTING_GUIDE.md**, Section 1.1-1.3

### "What does 'automation paused' mean?"
→ **COMMUNICATION_WORKFLOW.md**, Section 5
→ **TMUX_IO_MECHANICS.md**, Section 6

### "How do I debug a failing response?"
→ **TROUBLESHOOTING_GUIDE.md**, Section 2 & 3

### "What's the expected timing for a command?"
→ **COMMUNICATION_WORKFLOW.md**, Section 7
→ **TMUX_IO_MECHANICS.md**, Section 12

### "How can I make the system faster?"
→ **TROUBLESHOOTING_GUIDE.md**, Section 6

### "What configuration options affect I/O?"
→ **TROUBLESHOOTING_GUIDE.md**, Section 4

---

## 🛠️ Key Files in the Codebase

These documents reference the following source files:

### Core Orchestration
- `src/orchestrator/orchestrator.py` - Main orchestrator class
- `src/orchestrator/conversation_manager.py` - Turn-taking & response handling
- `src/orchestrator/context_manager.py` - Conversation history
- `src/orchestrator/message_router.py` - AI-to-AI messaging

### Controller & Tmux
- `src/controllers/tmux_controller.py` - Tmux session management
- `src/controllers/session_backend.py` - Abstract interface
- `src/controllers/claude_controller.py` - Claude-specific config
- `src/controllers/gemini_controller.py` - Gemini-specific config

### Utilities
- `src/utils/output_parser.py` - Response parsing & validation
- `src/utils/config_loader.py` - Configuration management
- `src/utils/logger.py` - Logging setup
- `src/utils/health_check.py` - Session health monitoring
- `src/utils/auto_restart.py` - Session auto-restart logic

### Configuration
- `config.yaml` - Main configuration file
- `CLAUDE.md`, `GEMINI.md` - AI-specific instructions

---

## ✅ Quick Validation Checklist

After reading the documentation, verify you understand:

- [ ] How a prompt gets sent to an AI via tmux (Section 2)
- [ ] How output is captured from the pane (Section 3)
- [ ] What happens when a human attaches to tmux (Section 5)
- [ ] Why commands are queued and how they're resumed (Section 7)
- [ ] How the orchestrator determines if automation should pause (Section 6)
- [ ] What causes response validation to fail (TMUX section 9)
- [ ] How to read the logs to understand what's happening (Troubleshooting section 2)
- [ ] How to diagnose "command is hanging" (Troubleshooting section 1.1)

---

## 📞 Getting Help

### If the docs don't answer your question:

1. **Check the glossary** (Troubleshooting section 9)
2. **Search the docs** for your term (use grep or Ctrl+F)
3. **Look at logs** in `logs/orchestrator.log` (format: Troubleshooting section 2)
4. **Run a test case** (Troubleshooting section 7.3)
5. **Inspect live** using manual tmux commands (Troubleshooting section 3.1)

### For issues:

1. **Identify symptom** → Troubleshooting section 1
2. **Check logs** → Troubleshooting section 2
3. **Trace command** → Troubleshooting section 3
4. **Implement fix** → Relevant section in COMMUNICATION_WORKFLOW or TMUX_IO_MECHANICS

---

## 📝 Document Updates

**Last Updated**: 2025-02-12
**Scope**: Covers orchestrator version with:
- Multi-AI support (Claude, Gemini, Codex, Qwen)
- Automation pause/resume on manual attach
- Response parsing & validation
- Turn-based conversation management
- Web API integration (via web_api.py)

**This documentation does NOT cover**:
- Human-in-the-loop features (separate doc: Human_In_The_Loop_Doc_Overview.md)
- Web UI frontend (separate docs in frontend/)
- Task orchestration (separate doc: Task_Orchestration.md if exists)
- Advanced features like checkpoints, escalation (covered in COMMUNICATION_WORKFLOW section 4.2)

---

## 🎓 Learning Path

**Beginner** (1-2 hours):
1. Read COMMUNICATION_WORKFLOW.md sections 1-3
2. Skim TMUX_IO_MECHANICS.md sections 1-2
3. Review quick reference card (Troubleshooting)

**Intermediate** (3-5 hours):
1. Read all of COMMUNICATION_WORKFLOW.md
2. Read TMUX_IO_MECHANICS.md sections 1-6
3. Work through Troubleshooting section 3 (manual trace)

**Advanced** (5+ hours):
1. Deep dive into source code files listed above
2. Read all three documents
3. Run integration tests and inspect logs
4. Modify config.yaml and observe effects

---

## 🚀 Next Steps

After reading this documentation:

1. **Run a test discussion** to see the system in action:
   ```bash
   PYTHONPATH=. python3 examples/run_orchestrated_discussion.py \
     "Test topic" --auto-start --max-turns 2 --log-file logs/test.log
   ```

2. **Attach to tmux** to trigger automation pause:
   ```bash
   tmux attach -t claude  # Pause triggered
   # (Press Ctrl+B, then D to detach and resume)
   ```

3. **Inspect logs** to understand the flow:
   ```bash
   tail -f logs/test.log | grep -E "dispatch|paused|response"
   ```

4. **Read the source code** for the most detailed understanding
   - Start with `orchestrator.py` and `conversation_manager.py`
   - Then read `tmux_controller.py` for I/O details
   - Finally review `output_parser.py` for parsing logic

---

**Happy exploring! 🎯**

For specific questions, refer to the appropriate document section using the map above.

