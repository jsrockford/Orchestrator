# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a proof-of-concept for programmatically interacting with Claude Code CLI running in WSL while maintaining manual user interaction capability. The goal is to test and validate methods for sending automated commands, capturing responses, and enabling multi-AI orchestration.

## Critical Working Directory Rules

**IMPORTANT**: Follow these directory rules strictly:

1. **Project Repository**: `/home/dgray/Projects/Orchestrator`
   - This is the ONLY directory where code changes should be made
   - All edits, new files, and modifications MUST be in this directory
   - NEVER make changes outside this directory

2. **Test Worktree Directory**: `/home/dgray/Projects/TestOrch`
   - This is a separate worktree for testing purposes
   - The user maintains fresh copies of code here for testing
   - The user is responsible for running tests in this directory
   - DO NOT modify files in this directory unless explicitly instructed

3. **Virtual Environment**: `venv`
   - The project uses a Python virtual environment named `venv`
   - Always ask the user before running Python project code
   - Be mindful of virtual environment activation when suggesting commands

## Architecture

The POC implements three controller approaches to interact with Claude Code:

1. **Tmux-Based Control** (Primary approach)
   - Creates isolated tmux sessions for Claude Code
   - Sends commands via `tmux send-keys`
   - Captures output using `tmux capture-pane`
   - Allows detaching/attaching for manual interaction

2. **Expect-Based Control** (Secondary approach)
   - Uses expect scripts with pexpect (Python) or similar
   - Pattern-based command/response interaction
   - Supports transition to manual mode via `interact()`

3. **PTY-Based Control** (Tertiary approach)
   - Direct pseudo-terminal manipulation
   - Lower-level control over Claude Code process
   - Read/write to master PTY file descriptor

### Core Components

- **Controllers**: Session management and command injection (`controllers/tmux_controller.py`, `expect_controller.py`, `pty_controller.py`)
- **Output Parser**: Response extraction and timing detection (`utils/output_parser.py`)
- **Session Monitor**: Status tracking and health checks

## Project Structure

```
claude-interaction-poc/
├── src/
│   ├── main.py                    # Entry point
│   ├── controllers/               # Three controller implementations
│   │   ├── tmux_controller.py
│   │   ├── expect_controller.py
│   │   └── pty_controller.py
│   ├── utils/
│   │   ├── output_parser.py       # Response parsing logic
│   │   └── logger.py
│   └── tests/                     # Test suites (basic, complex, switching, errors)
├── config.yaml                    # Session timeouts, prompts, test commands
├── logs/                          # Debug and interaction logs
└── examples/                      # Sample interaction scripts
```

## Development Approach

### Implementation Priority
1. Start with tmux controller (most reliable)
2. Test simple commands before complex multi-turn interactions
3. Log all interactions for debugging
4. Implement each test suite incrementally (T1-T4)

### Key Technical Challenges
- **Prompt Detection**: Identifying when Claude Code is ready for input vs processing
- **Response Boundaries**: Determining when output is complete
- **Timing**: Handling Claude Code's variable response latency (startup: ~5s, commands: variable)
- **Context Preservation**: Maintaining conversation state between automated/manual modes

## Configuration (config.yaml)

Critical parameters:
- `claude.startup_timeout`: Wait time for Claude initialization (default: 10s)
- `claude.response_timeout`: Max wait for command response (default: 30s)
- `claude.prompt_pattern`: Regex to detect input-ready state (default: ">")
- `tmux.session_name`: Unique session identifier
- `tmux.capture_lines`: Buffer size for output capture (default: 100)

## Testing Strategy

### Test Suites
- **T1 (Basic)**: Session lifecycle, simple commands, output verification
- **T2 (Complex)**: File operations, multi-turn context, working directory
- **T3 (Switching)**: Auto→manual→auto transitions, session persistence
- **T4 (Error Handling)**: Missing dependencies, session conflicts, crashes, timeouts

### Success Metrics
- Command delivery: <100ms latency, >95% success rate
- Output capture: <500ms latency, >90% success rate
- Session stability: 1 hour operation without crashes

## WSL-Specific Considerations
- Test in WSL2 environment (Ubuntu)
- Path handling: `/mnt/c/` for Windows paths
- Tmux must be installed in WSL
- Claude Code must be properly configured in WSL PATH

## Questions to Answer Through Implementation
1. Does Claude Code have a consistent prompt pattern for detecting ready state?
2. How does Claude indicate processing vs awaiting input?
3. What is the maximum reliable command length?
4. How does rapid command queuing affect response quality?
5. Can we detect streaming response completion reliably?

## Task Completion Protocol
**IMPORTANT**: When completing tasks or phases of work:
1. Update Tasks.md to mark items as complete
2. Check off subtasks within each phase
3. Add completion notes with any relevant details
4. Commit documentation updates along with code changes

This ensures project status is always accurately reflected and makes it easy to resume work in future sessions.
