# Task List: Context Management Implementation

## Overview
This document tracks the implementation of the [[CLEAR]] marker system for universal context management across all AI models in orchestrated sessions. This addresses token exhaustion during Phase 3 (Implementation) workflows by providing orchestrator-mediated context clearing.

**Goal:** Enable all AI models to signal when context should be cleared, with the Orchestrator executing the clear command and prompting file re-reads, regardless of individual model CLI capabilities.

**References:**
- MessageBoard.md discussion (lines 9-191)
- templates/overview.md (Phase 3 workflow)

---

## Phase 1: Core Orchestrator Implementation

### 1.1 [[CLEAR]] Signal Detection
- [ ] Add [[CLEAR]] pattern detection to `src/orchestrator/conversation_manager.py`
  - [ ] Implement regex to match: `[[CLEAR]]`, `[[CLEAR:claude]]`, `[[CLEAR:codex]]`, `[[CLEAR:gemini]]`, `[[CLEAR:qwen]]`, `[[CLEAR:all]]`
  - [ ] Extract target agent(s) from scoped signals
  - [ ] **DECISION:** Handle unscoped `[[CLEAR]]` as emitting agent only (for safety)

### 1.2 Context Validation & Safety
- [ ] Implement context validation rules (WHITELIST approach)
  - [ ] Only honor [[CLEAR]] in orchestrated discussion turns
  - [ ] Only honor [[CLEAR]] in MessageBoard.md posts
  - [ ] Ignore [[CLEAR]] in all other files (PRD.md, source code, docs, comments)
  - [ ] Use whitelist of valid contexts (orchestrated_turn, MessageBoard.md) rather than file pattern blacklist
- [ ] Implement debounce/cooldown mechanism
  - [ ] Track last clear timestamp per agent
  - [ ] Enforce 30-second minimum between clears for same agent
  - [ ] Log and skip clears that violate cooldown

### 1.3 Clear Execution Logic
- [ ] Implement clear command execution in orchestrator
  - [ ] **IMPORTANT:** Use model-specific clear commands:
    - Claude: `/clear`
    - Gemini: `/clear`
    - Qwen: `/clear`
    - Codex: `/new` (NOT /clear)
  - [ ] Send appropriate clear command to target tmux session(s) via controller
  - [ ] Handle [[CLEAR:all]] to clear all active agents
  - [ ] Handle scoped clears for individual agents
  - [ ] Add error handling for failed clear attempts
- [ ] Implement post-clear prompt injection
  - [ ] Construct prompt: "Context cleared. Re-read PRD.md, ARCHITECTURE.md, and the next section of PROJECT_TASKS.md before continuing."
  - [ ] Note: Section number determination deferred (no reliable resolver yet; keep prompt generic)
  - [ ] Send prompt to cleared agent(s) immediately after clear
  - [ ] Wait for agent ready state before injecting prompt

### 1.4 Logging & Monitoring
- [ ] Create dedicated context clear log file: `logs/context_clears.log`
- [ ] Log all clear events with:
  - [ ] Timestamp
  - [ ] Agent(s) cleared
  - [ ] Trigger source (which model emitted the signal)
  - [ ] Context (turn number, current phase, current task section if available)
  - [ ] Success/failure status
- [ ] Add clear event counters to orchestrator status endpoint
  - [ ] Total clears per session
  - [ ] Clears per agent
  - [ ] Last clear timestamp per agent

### 1.5 Testing
- [ ] Unit tests for signal detection
  - [ ] Test regex matches all valid [[CLEAR]] formats
  - [ ] Test extraction of target agents from scoped signals
  - [ ] Test rejection of invalid signal formats
- [ ] Unit tests for context validation
  - [ ] Test signals in MessageBoard.md are honored
  - [ ] Test signals in orchestrated turns are honored
  - [ ] Test signals in repo files are ignored
- [ ] Unit tests for debounce logic
  - [ ] Test cooldown enforcement
  - [ ] Test clears allowed after cooldown expires
- [ ] Integration tests
  - [ ] Test manual [[CLEAR]] emission during live orchestration
  - [ ] Test clear command reaches tmux session
  - [ ] Test post-clear prompt injection
  - [ ] Test logging of clear events

---

## Phase 2: Documentation & Templates

### 2.1 Update Core Documentation
- [ ] Update `templates/overview.md`
  - [ ] Add [[CLEAR]] marker to Phase 3 "Iterative Development" section (lines 167-175)
  - [ ] Document checkpoint protocol with [[CLEAR]] emission
  - [ ] Add [[CLEAR]] to "Key Principles for AI Models" section
  - [ ] Add examples of when to emit [[CLEAR]]
- [ ] Update `docs/architecture.md`
  - [ ] Document [[CLEAR]] signal flow through orchestrator components
  - [ ] Add sequence diagram for clear signal → execution → re-read
- [ ] Create `docs/Context_Management_Guide.md`
  - [ ] Explain token exhaustion problem
  - [ ] Document [[CLEAR]] marker syntax and usage
  - [ ] Provide examples of checkpoint meta-tasks
  - [ ] Explain orchestrator's role in executing clears
  - [ ] List safety guardrails and validation rules

### 2.2 Phase 2 Instruction Files (Planning Phase)
- [ ] Create or update Architect instruction file
  - [ ] Add guidance to include CHECKPOINT sections in PROJECT_TASKS.md
  - [ ] Provide template for checkpoint meta-tasks
  - [ ] Example: "### CHECKPOINT: Auth Module Complete - Emit [[CLEAR:codex]] and re-read PRD/ARCH before starting Data Layer"
- [ ] Create or update Project Manager instruction file
  - [ ] Add requirement to insert checkpoints at logical boundaries
  - [ ] Suggest checkpoint frequency (e.g., after every 3-5 major tasks or major architectural sections)
  - [ ] Document how to estimate optimal checkpoint placement based on task complexity

### 2.3 Phase 3 Instruction Files (Implementation Phase)
- [ ] Create or update Lead Developer instruction file
  - [ ] Explain when to emit [[CLEAR:modelname]]
    - [ ] After completing checkpoint sections in PROJECT_TASKS.md
    - [ ] When token usage reaches 60-70% of budget
    - [ ] After completing any major task cluster (3+ related tasks)
  - [ ] Document post-clear protocol: update PROJECT_TASKS.md, emit signal, wait for clear, re-read files
  - [ ] Provide examples of [[CLEAR]] emission in MessageBoard posts
  - [ ] Emphasize: clearing does NOT lose progress (files are source of truth)
- [ ] Create or update Code Reviewer instruction file
  - [ ] Add checkpoint awareness for review workflows
  - [ ] Suggest clearing before starting review of new module
- [ ] Update existing CLAUDE.md, GEMINI.md, CODEX.md, QWEN.md files
  - [ ] Add [[CLEAR]] marker documentation
  - [ ] Provide model-specific guidance on when to emit signal
  - [ ] Reference Context_Management_Guide.md for details

### 2.4 Template Creation
- [ ] Create `templates/PROJECT_TASKS_with_checkpoints.md` template
  - [ ] Example task list structure with embedded checkpoints
  - [ ] Show checkpoint placement at section boundaries
  - [ ] Include example meta-tasks with [[CLEAR]] emission instructions
- [ ] Create `templates/CHECKPOINT_meta_task.md` snippet
  - [ ] Reusable checkpoint task format
  - [ ] Fields: section completed, target agent, files to re-read, next section preview

---

## Phase 3: Optional Enhancements (DEFERRED - Not in MVP)

### 3.1 Turn-Count Check-In (Gemini's Proposal) - BACKLOG
- [ ] Add turn counter to conversation_manager.py
  - [ ] Track turns per agent in current session
  - [ ] Make check-in interval configurable in config.yaml (default: 10-15 turns)
- [ ] Implement check-in prompt injection
  - [ ] After N turns, inject: "System Check: You have completed N turns. Review your progress in PROJECT_TASKS.md. If this is a logical checkpoint, reply with [[CLEAR:yourname]] to clear context. Otherwise reply with /continue to proceed."
  - [ ] Parse agent response for [[CLEAR]] signal or /continue command
  - [ ] Log check-in events and responses
- [ ] Configuration options
  - [ ] Enable/disable turn-count check-in globally
  - [ ] Per-agent turn thresholds
  - [ ] Check-in prompt customization

### 3.2 Clear Analytics & Optimization - BACKLOG
- [ ] Add clear analytics dashboard
  - [ ] Average clears per session
  - [ ] Tokens saved per clear (estimated)
  - [ ] Checkpoint effectiveness metrics
  - [ ] Agent-specific clear patterns
- [ ] Implement clear recommendations
  - [ ] Analyze task completion rate vs clear frequency
  - [ ] Suggest optimal checkpoint placement in retrospective
  - [ ] Warn if agent hasn't cleared in X turns despite high token usage

### 3.3 Web UI Integration - BACKLOG
- [ ] Add [[CLEAR]] controls to Web UI
  - [ ] Manual clear button per agent
  - [ ] Display last clear timestamp
  - [ ] Show clear event history in timeline
  - [ ] Visual indicator when agent approaches token budget limit
- [ ] Real-time clear notifications
  - [ ] Toast/notification when orchestrator executes clear
  - [ ] Display post-clear re-read prompt in UI
  - [ ] Show cooldown timer if clear attempted too soon

---

## Configuration Changes

### config.yaml additions
```yaml
context_management:
  enabled: true
  clear_signal: "[[CLEAR]]"
  debounce_seconds: 30

  # Context validation - WHITELIST approach
  # Only honor [[CLEAR]] signals in these contexts
  valid_contexts:
    - "orchestrated_turn"    # During orchestrated discussions
    - "MessageBoard.md"      # When posted to MessageBoard

  # Supported agents and their clear commands
  agents:
    claude:
      clear_command: "/clear"
    gemini:
      clear_command: "/clear"
    qwen:
      clear_command: "/clear"
    codex:
      clear_command: "/new"  # Codex uses /new instead of /clear

  # Post-clear behavior
  post_clear_prompt: "Context cleared. Re-read PRD.md, ARCHITECTURE.md, and the next section of PROJECT_TASKS.md before continuing."
  required_rereads:
    - "PRD.md"
    - "ARCHITECTURE.md"
    - "PROJECT_TASKS.md"

  # Turn-count check-in (OPTIONAL - deferred to Phase 3)
  turn_count_checkin:
    enabled: false
    interval: 12
    prompt: "System Check: You have completed {turn_count} turns. Review your progress in PROJECT_TASKS.md. If this is a logical checkpoint, reply with [[CLEAR:{agent}]] to clear context. Otherwise reply with /continue to proceed."

  # Logging
  log_file: "logs/context_clears.log"
  log_level: "INFO"
```

---

## Success Criteria

- [ ] All AI models (Claude, Gemini, Codex, Qwen) can trigger context clears via [[CLEAR]] signal
- [ ] Orchestrator correctly detects and executes clear commands
- [ ] Safety guardrails prevent accidental clears from repo files
- [ ] Debounce prevents rapid-fire clears
- [ ] Post-clear prompts successfully guide agents to re-read source files
- [ ] All clear events are logged with full context
- [ ] Phase 2/3 instruction files document when and how to use [[CLEAR]]
- [ ] Templates include checkpoint examples with [[CLEAR]] emission
- [ ] Integration tests validate end-to-end clear workflow
- [ ] Documentation is complete and clear for human operators and AI models

---

## Notes & Decisions

**Decision Log:**
- 2025-11-24: Adopted [[CLEAR]] marker approach over self-clearing due to Codex inability to self-clear
- 2025-11-24: Team consensus on scoped signals ([[CLEAR:agent]]) and safety guardrails
- 2025-11-24: Agreed on 30-second debounce and context validation (orchestrated turns + MessageBoard only)

**Decisions Made:**
- **Unscoped `[[CLEAR]]`:** Clears only the emitting agent (for safety). Use [[CLEAR:all]] to clear all agents.
- **Partial clears:** REMOVED from scope per Don's request. We do NOT use Aider; focusing on full clears only.
- **Mid-task [[CLEAR]]:** Honor but log as warning (Gemini's recommendation). Gives agent escape hatch if stuck.
- **CLI Tools:** Claude Code CLI, Codex CLI, Gemini CLI, Qwen CLI (NOT Aider)

**Dependencies:**
- Requires existing orchestrator conversation management infrastructure
- Requires tmux controller clear command support:
  - Claude Code CLI: `/clear` - Verified working
  - Gemini CLI: `/clear` - Verified working
  - Qwen CLI: `/clear` - Verified working
  - Codex CLI: `/new` - **IMPORTANT: Uses different command than other CLIs**
- Phase 2/3 instruction files are conceptual and need to be created

**MVP Scope (Phase 1-2):**
Phase 1 (Core Implementation) and Phase 2 (Documentation) constitute the MVP. Phase 3 enhancements are deferred to post-MVP backlog.

---

**Last Updated:** 2025-11-24
**Status:** Planning - Not Yet Started
**Owner:** Don (Human), with Claude, Gemini, Codex support
