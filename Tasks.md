# Claude Code WSL Interaction POC - Task List

## Phase 1: Discovery & Minimal Tmux Controller ✅ COMPLETE

### Task 1.1: Environment Verification ✅
- [x] Verify tmux is installed in WSL2 (tmux 3.2a)
- [x] Verify Claude Code is accessible in PATH (/home/dgray/.nvm/versions/node/v24.7.0/bin/claude)
- [x] Test manual tmux session creation with Claude Code
- [x] Document startup behavior (timing, messages, prompt appearance)
- [x] **Critical Discovery**: Text and Enter must be sent as separate commands

### Task 1.2: Basic Tmux Controller Implementation ✅
- [x] Create project structure (src/, controllers/, utils/, tests/)
- [x] Implement `TmuxController` class with methods:
  - [x] `start_session()` - Launch Claude Code in named tmux session (with auto trust confirmation)
  - [x] `send_command()` - Send text to tmux pane (with separate Enter)
  - [x] `capture_output()` - Capture pane buffer
  - [x] `capture_scrollback()` - Capture entire scrollback buffer
  - [x] `session_exists()` - Check if session is running
  - [x] `kill_session()` - Terminate session cleanly
  - [x] `send_ctrl_c()` - Cancel current operation
  - [x] `attach_for_manual()` - Support for manual interaction
  - [x] `get_status()` - Session status information
  - [x] `wait_for_ready()` - **NEW**: Detect when response is complete

### Task 1.3: Output Detection Strategy ✅
- [x] Experiment with timing-based approach (wait N seconds after command)
- [x] Test buffer size requirements for typical responses (100 lines sufficient)
- [x] Identify patterns that indicate response completion (output stabilization)
- [x] Document Claude Code's output behavior patterns (FINDINGS.md)
- [x] **Implemented**: `wait_for_ready()` using output stabilization detection

### Task 1.4: Manual Testing & Observation ✅
- [x] Send simple commands ("What is 2 + 2?", "What is Python?")
- [x] Measure actual response times (varies, ~2-5 seconds)
- [x] Capture screenshots/logs of various interaction states
- [x] Document findings: startup time (~8 seconds), response patterns, edge cases
- [x] Live observation testing with tmux attach -r

### Task 1.5: Configuration Setup ✅
- [x] Create `config.yaml` with discovered values:
  - Actual startup timeout needed (8 seconds)
  - Realistic response timeout (30 seconds)
  - Tmux session settings
  - Buffer capture size (100 lines)
  - Test commands for validation
- [x] Implement config loader in utils (ConfigLoader with dot notation)
- [x] Add PyYAML dependency
- [x] Create test_config.py for validation

### Task 1.6: Basic Test Suite (Post-Discovery) ✅
- [x] Write test for session start/stop lifecycle (test_controller_auto.py)
- [x] Write test for simple command delivery
- [x] Write test for output capture (verify we get *some* output)
- [x] Write test for session cleanup
- [x] **Additional**: Manual interactive test with live observation (test_manual_together.py)

## Phase 2: Refinement & Reliability

### Task 2.1: Response Completion Detection ✅
- [x] Implement timing-based detector (wait for output to stabilize) - `wait_for_ready()`
- [x] Add configurable delays between captures (check_interval parameter)
- [x] Test with various command types (quick vs slow responses) - all working

### Task 2.2: Output Parser ✅
- [x] Create `OutputParser` class
- [x] Implement methods to:
  - [x] Strip ANSI codes/formatting
  - [x] Remove UI elements (headers, separators, status)
  - [x] Extract Q&A pairs from conversation
  - [x] Get last question/response
  - [x] Detect error states
  - [x] Format conversation in readable Q&A format
- [x] Create test_output_parser.py with real Claude output
- [x] All parsing functions validated and working

### Task 2.3: Error Handling
- [ ] Handle "session already exists" scenario
- [ ] Handle Claude Code not found
- [ ] Handle tmux not installed
- [ ] Handle command timeout
- [ ] Add retry logic for failed commands

### Task 2.4: Advanced Test Suite
- [ ] Test multi-turn conversations (context preservation)
- [ ] Test file operation commands
- [ ] Test rapid sequential commands
- [ ] Test error scenarios

## Phase 3: Manual/Auto Switching

### Task 3.1: Session Attachment ✅
- [x] Implement `attach_for_manual()` method
- [x] Test attaching to running session (read-only mode working)
- [x] Test detaching and resuming automation
- [x] Verify state preservation after manual interaction (confirmed working)

### Task 3.2: Switching Tests
- [ ] Test automated → manual → automated workflow
- [ ] Verify command history is maintained
- [ ] Test edge cases (attach during command processing)

## Phase 4: Gemini CLI Integration

### Task 4.1: Architecture Refactoring
- [ ] Create GeminiDev git branch for safe development
- [ ] Refactor TmuxController to be AI-agnostic
- [ ] Create base class structure for multi-AI support
- [ ] Update config.yaml with Gemini-specific settings
- [ ] Ensure Claude Code functionality remains intact

### Task 4.2: Gemini Controller Implementation
- [ ] Create GeminiController class
- [ ] Test Gemini CLI startup behavior and timing
- [ ] Implement Gemini-specific prompt patterns
- [ ] Adapt wait_for_ready() for Gemini's output patterns
- [ ] Create separate tmux session management for Gemini

### Task 4.3: Gemini Testing & Validation
- [ ] Create worktree for Gemini testing (similar to Claude worktree)
- [ ] Test Gemini session start/stop lifecycle
- [ ] Test command injection and response capture
- [ ] Verify wait_for_ready() works with Gemini
- [ ] Manual observation testing with tmux attach -r

### Task 4.4: Dual AI Operation
- [ ] Test running Claude and Gemini sessions simultaneously
- [ ] Verify separate tmux sessions don't interfere
- [ ] Test switching between AI sessions
- [ ] Validate output parsing works for both AIs
- [ ] Create demo showing both AIs operating in parallel

### Task 4.5: Multi-AI Orchestration Foundation
- [ ] Design orchestrator pattern for AI-to-AI communication
- [ ] Implement message passing between Claude and Gemini
- [ ] Test collaborative workflows
- [ ] Add user intervention capability during AI interactions
- [ ] Document orchestration patterns and use cases

## Phase 5: Documentation & Results

### Task 5.1: Results Documentation
- [ ] Document success rates for each test
- [ ] Record actual performance metrics (latency, reliability)
- [ ] Create comparison table vs spec requirements
- [ ] Document discovered Claude Code behaviors

### Task 5.2: Usage Examples
- [ ] Create example script: simple command
- [ ] Create example script: file context workflow
- [ ] Create example script: manual switching
- [ ] Add inline comments explaining key points

### Task 5.3: Troubleshooting Guide
- [ ] Document common issues encountered
- [ ] Provide solutions/workarounds
- [ ] List known limitations
- [ ] Add debugging tips

## Key Findings to Document

### Claude Code Behavior ✅
- **Prompt Pattern**: `>` appears immediately, even while thinking
- **Startup Time**: ~8 seconds (3s for trust, 3s for initialization)
- **Response Indicators**: Output stabilization detection (wait_for_ready)
- **Output Format**: Text with unicode box drawing, ANSI codes present
- **Critical**: Text and Enter must be separate tmux send-keys commands

### Timing Baselines (measured) ✅
- Session startup: ~8 seconds
- Simple command response: 2-5 seconds (varies by complexity)
- Complex command response: 5-10+ seconds
- Buffer stabilization time: 1.5 seconds (3 checks @ 0.5s each)

### Critical Discoveries ✅
- [x] Can we detect "thinking" vs "ready" state? **YES** - Output stabilization works
- [x] Is there output when commands complete? **YES** - Returns to prompt with separators
- [x] How does Claude Code handle rapid commands? **ISSUE FOUND & FIXED** - Commands sent too fast overlap on same line; wait_for_ready() solves this
- [x] What indicates an error vs normal response? **TBD** - Need more testing with errors

## Success Criteria Checklist

- [x] Can start Claude Code in tmux session programmatically ✅
- [x] Can send commands reliably (>95% success rate) ✅ 100% in testing
- [x] Can capture full responses (>90% success rate) ✅ 100% in testing
- [x] Can switch between automated and manual modes ✅ tmux attach -r working
- [ ] Session remains stable for 1+ hour - Not yet tested
- [x] Command latency < 100ms ✅ ~0.1ms measured
- [x] Output capture latency < 500ms ✅ ~10ms measured
