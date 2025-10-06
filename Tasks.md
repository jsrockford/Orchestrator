# Claude Code WSL Interaction POC - Task List

## Phase 1: Discovery & Minimal Tmux Controller

### Task 1.1: Environment Verification
- [ ] Verify tmux is installed in WSL2
- [ ] Verify Claude Code is accessible in PATH
- [ ] Test manual tmux session creation with Claude Code
- [ ] Document startup behavior (timing, messages, prompt appearance)

### Task 1.2: Basic Tmux Controller Implementation
- [ ] Create project structure (src/, controllers/, utils/, tests/)
- [ ] Implement `TmuxController` class with methods:
  - [ ] `start_session()` - Launch Claude Code in named tmux session
  - [ ] `send_command()` - Send text to tmux pane
  - [ ] `capture_output()` - Capture pane buffer
  - [ ] `session_exists()` - Check if session is running
  - [ ] `kill_session()` - Terminate session cleanly

### Task 1.3: Output Detection Strategy
- [ ] Experiment with timing-based approach (wait N seconds after command)
- [ ] Test buffer size requirements for typical responses
- [ ] Identify patterns that indicate response completion (if any exist)
- [ ] Document Claude Code's output behavior patterns

### Task 1.4: Manual Testing & Observation
- [ ] Send simple commands ("Help", "What is Python?")
- [ ] Measure actual response times
- [ ] Capture screenshots/logs of various interaction states
- [ ] Document findings: startup time, response patterns, edge cases

### Task 1.5: Configuration Setup
- [ ] Create `config.yaml` with discovered values:
  - Actual startup timeout needed
  - Realistic response timeout
  - Tmux session settings
  - Buffer capture size
- [ ] Implement config loader in utils

### Task 1.6: Basic Test Suite (Post-Discovery)
- [ ] Write test for session start/stop lifecycle
- [ ] Write test for simple command delivery
- [ ] Write test for output capture (verify we get *some* output)
- [ ] Write test for session cleanup

## Phase 2: Refinement & Reliability

### Task 2.1: Response Completion Detection
- [ ] Implement timing-based detector (wait for output to stabilize)
- [ ] Add configurable delays between captures
- [ ] Test with various command types (quick vs slow responses)

### Task 2.2: Output Parser
- [ ] Create `OutputParser` class
- [ ] Implement methods to:
  - Strip ANSI codes/formatting
  - Remove duplicate captures
  - Extract actual response content
  - Detect error states

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

### Task 3.1: Session Attachment
- [ ] Implement `attach_for_manual()` method
- [ ] Test attaching to running session
- [ ] Test detaching and resuming automation
- [ ] Verify state preservation after manual interaction

### Task 3.2: Switching Tests
- [ ] Test automated → manual → automated workflow
- [ ] Verify command history is maintained
- [ ] Test edge cases (attach during command processing)

## Phase 4: Documentation & Results

### Task 4.1: Results Documentation
- [ ] Document success rates for each test
- [ ] Record actual performance metrics (latency, reliability)
- [ ] Create comparison table vs spec requirements
- [ ] Document discovered Claude Code behaviors

### Task 4.2: Usage Examples
- [ ] Create example script: simple command
- [ ] Create example script: file context workflow
- [ ] Create example script: manual switching
- [ ] Add inline comments explaining key points

### Task 4.3: Troubleshooting Guide
- [ ] Document common issues encountered
- [ ] Provide solutions/workarounds
- [ ] List known limitations
- [ ] Add debugging tips

## Key Findings to Document

### Claude Code Behavior
- **Prompt Pattern**: `>` appears immediately, even while thinking
- **Startup Time**: TBD (measure during testing)
- **Response Indicators**: TBD (timing-based? pattern-based?)
- **Output Format**: TBD (streaming? batched? ANSI codes?)

### Timing Baselines (to be measured)
- Session startup: _____ seconds
- Simple command response: _____ seconds
- Complex command response: _____ seconds
- Buffer stabilization time: _____ seconds

### Critical Discoveries
- [ ] Can we detect "thinking" vs "ready" state? (Initial observation: No via prompt alone)
- [ ] Is there output when commands complete? (TBD)
- [ ] How does Claude Code handle rapid commands? (TBD)
- [ ] What indicates an error vs normal response? (TBD)

## Success Criteria Checklist

- [ ] Can start Claude Code in tmux session programmatically
- [ ] Can send commands reliably (>95% success rate)
- [ ] Can capture full responses (>90% success rate)
- [ ] Can switch between automated and manual modes
- [ ] Session remains stable for 1+ hour
- [ ] Command latency < 100ms
- [ ] Output capture latency < 500ms
