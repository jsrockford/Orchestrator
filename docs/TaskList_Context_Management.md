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
- [x] Add [[CLEAR]] pattern detection to `src/orchestrator/conversation_manager.py`
  - [x] Implement regex to match: `[[CLEAR]]`, `[[CLEAR:claude]]`, `[[CLEAR:codex]]`, `[[CLEAR:gemini]]`, `[[CLEAR:qwen]]`, `[[CLEAR:all]]`
    - Example: `CLEAR_PATTERN = r"\[\[CLEAR(?::(\w+|all))?\]\]"` (group 1 captures optional agent/all)
  - [x] Extract target agent(s) from scoped signals
  - [x] **DECISION:** Handle unscoped `[[CLEAR]]` as emitting agent only (for safety)
  - Implementation anchor: hook detection right after responses are parsed and before `turn_record` is appended in `ConversationManager.facilitate_discussion` (post-validation, before `_store_turn`). Capture `speaker`, `response`, and the emitting agent name for default targeting.

### 1.2 Context Validation & Safety
- [x] Implement context validation rules (WHITELIST approach)
  - [x] Only honor [[CLEAR]] in orchestrated discussion turns
  - [x] Only honor [[CLEAR]] in MessageBoard.md posts
  - [x] Ignore [[CLEAR]] in all other files (PRD.md, source code, docs, comments)
  - [x] Use whitelist of valid contexts (orchestrated_turn, MessageBoard.md) rather than file pattern blacklist
  - [x] Implement debounce/cooldown mechanism
  - [x] Track last clear timestamp per agent
  - [x] Enforce 30-second minimum between clears for same agent
  - [x] Log and skip clears that violate cooldown
  - Implementation anchor: maintain per-agent timestamps in `ConversationManager` (new dict alongside `_agent_activity`); enforcement happens in the same detection block before firing clears. For `[[CLEAR:all]]`, apply the per-agent cooldown as you iterate the target set.
  - Source tagging: mark signals with `source` field (`orchestrated_turn` when detected in a model response; `MessageBoard.md` when detected via MessageBoard poll/handler). Ignore any other sources.
  - MessageBoard detection: if MessageBoard polling/monitoring exists, reuse it to scan for `[[CLEAR]]` and feed the same handler with `source="MessageBoard.md"`; otherwise skip MessageBoard sources.

### 1.3 Clear Execution Logic
- [x] Implement clear command execution in orchestrator
  - [x] **IMPORTANT:** Use model-specific clear commands:
    - Claude: `/clear`
    - Gemini: `/clear`
    - Qwen: `/clear`
    - Codex: `/new` (NOT /clear)
  - [x] Dispatch clears via existing controller path (`orchestrator.dispatch_command`) using controller `send_command`/`send_macro` for slash commands. No new transport needed.
  - [x] Send appropriate clear command to target tmux session(s) via controller
  - [x] Handle [[CLEAR:all]] to clear all active agents
  - [x] Handle scoped clears for individual agents
  - [x] Debounce applies per agent, including when [[CLEAR:all]] is broadcast
  - [x] Add error handling for failed clear attempts (log failures; surface in status snapshot; rely on controller retries)
  - [x] Implement post-clear prompt injection
    - [x] Construct prompt: "Context cleared. Re-read PRD.md, ARCHITECTURE.md, and the next section of PROJECT_TASKS.md before continuing."
    - [x] Note: Section number determination deferred (no reliable resolver yet; keep prompt generic)
    - [x] Send prompt to cleared agent(s) immediately after clear
    - [x] Wait for agent ready state before injecting prompt
  - Implementation anchor:
    - Create a helper (e.g., `_handle_clear_signal`) that maps targets → commands, calls `orchestrator.dispatch_command(target, clear_cmd)`, then queues an injected message via `inject_message` for the same target with the post-clear prompt. Invoke this helper from the detection block in `facilitate_discussion`.
    - Controllers already translate dispatches to tmux via `TmuxController.send_command`/`send_macro`, so no direct tmux calls from the manager.
  - Error handling: on dispatch failure, log ERROR to `context_clears.log`, update status snapshot with `last_failure` (timestamp/reason), and continue without blocking the emitting model’s run loop.

### 1.4 Logging & Monitoring
- [x] Create dedicated context clear log file: `logs/context_clears.log`
- [x] Log all clear events with:
  - [x] Timestamp
  - [x] Agent(s) cleared
  - [x] Trigger source (which model emitted the signal)
  - [x] Context (turn number, current phase, current task section if available)
  - [x] Success/failure status
- [x] Add clear event counters to orchestrator status snapshot (extends `ConversationManager.get_status_snapshot`, also used by control channel status file when enabled)
  - [x] Total clears per session
  - [x] Clears per agent
  - [x] Last clear timestamp per agent
  - Implementation anchor:
    - Extend `ConversationManager.get_status_snapshot()` to include a `clear_stats` dict with fields: `total`, `per_agent` (mapping), `last_clear_ts` (mapping), and optionally `last_failure` info.
    - During clear handling, append structured entries to the clear log and update these counters. `_refresh_status_snapshot()` already writes the status file when enabled; piggyback on that.

### 1.5 Testing
- [x] Unit tests for signal detection
  - [x] Test regex matches all valid [[CLEAR]] formats
  - [x] Test extraction of target agents from scoped signals
  - [x] Test rejection of invalid signal formats
- [x] Unit tests for context validation
  - [x] Test signals in MessageBoard.md are honored
  - [x] Test signals in orchestrated turns are honored
  - [x] Test signals in repo files are ignored
- [x] Unit tests for debounce logic
  - [x] Test cooldown enforcement
  - [x] Test clears allowed after cooldown expires
- [x] Integration tests
  - [x] Test manual [[CLEAR]] emission during live orchestration
  - [x] Test clear command reaches tmux session
  - [x] Test post-clear prompt injection
  - [x] Test logging of clear events
  - Implementation anchor for tests:
    - Place unit tests under `tests/` (e.g., `test_conversation_manager_clear.py`) mocking controllers (`orchestrator.dispatch_command`) and using fake participant metadata.
    - For integration, mimic a `ConversationManager` with a stub controller that records commands and injected messages; simulate responses containing [[CLEAR]] and assert dispatch + prompt injection + cooldown enforcement.

---

## Phase 2: Documentation & Templates

### 2.1 Update Core Documentation
- [x] Update `templates/overview.md`
  - [x] Add [[CLEAR]] marker to Phase 3 "Iterative Development" section (lines 167-175)
  - [x] Document checkpoint protocol with [[CLEAR]] emission
  - [x] Add [[CLEAR]] to "Key Principles for AI Models" section
  - [x] Add examples of when to emit [[CLEAR]]
- [x] Update `docs/architecture.md`
  - [x] Document [[CLEAR]] signal flow through orchestrator components
  - [x] Add sequence diagram for clear signal → execution → re-read
- [x] Create `docs/Context_Management_Guide.md`
  - [x] Explain token exhaustion problem
  - [x] Document [[CLEAR]] marker syntax and usage
  - [x] Provide examples of checkpoint meta-tasks
  - [x] Explain orchestrator's role in executing clears
  - [x] List safety guardrails and validation rules

### 2.2 Phase 2 Instruction Files (Planning Phase)
- [x] Create or update Architect instruction file
  - [x] Add guidance to include CHECKPOINT sections in PROJECT_TASKS.md
  - [x] Provide template for checkpoint meta-tasks
  - [x] Example: "### CHECKPOINT: Auth Module Complete - Emit [[CLEAR:codex]] and re-read PRD/ARCH before starting Data Layer"
- [x] Create or update Project Manager instruction file
  - [x] Add requirement to insert checkpoints at logical boundaries
  - [x] Suggest checkpoint frequency (e.g., after every 3-5 major tasks or major architectural sections)
  - [x] Document how to estimate optimal checkpoint placement based on task complexity

### 2.3 Phase 3 Instruction Files (Implementation Phase)
- [x] Create or update Lead Developer instruction file
  - [x] Explain when to emit [[CLEAR:modelname]]
    - [x] After completing checkpoint sections in PROJECT_TASKS.md
    - [x] When token usage reaches 60-70% of budget
    - [x] After completing any major task cluster (3+ related tasks)
  - [x] Document post-clear protocol: update PROJECT_TASKS.md, emit signal, wait for clear, re-read files
  - [x] Provide examples of [[CLEAR]] emission in MessageBoard posts
  - [x] Emphasize: clearing does NOT lose progress (files are source of truth)
- [x] Create or update Code Reviewer instruction file
  - [x] Add checkpoint awareness for review workflows
  - [x] Suggest clearing before starting review of new module
- [ ] Update existing CLAUDE.md, GEMINI.md, CODEX.md, QWEN.md files
  - [ ] Add [[CLEAR]] marker documentation
  - [ ] Provide model-specific guidance on when to emit signal
  - [ ] Reference Context_Management_Guide.md for details

### 2.4 Template Creation
- [x] Create `templates/PROJECT_TASKS_with_checkpoints.md` template
  - [x] Example task list structure with embedded checkpoints
  - [x] Show checkpoint placement at section boundaries
  - [x] Include example meta-tasks with [[CLEAR]] emission instructions
- [x] Create `templates/CHECKPOINT_meta_task.md` snippet
  - [x] Reusable checkpoint task format
  - [x] Fields: section completed, target agent, files to re-read, next section preview

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

## Phase 4: Instruction Generator Integration
- [x] Update `scripts/generate_instruction_files.py` to embed token-management guidance
  - [x] Add checkpoint/CLEAR responsibilities to Planning roles (Architect/EngineeringManager/TechnicalLead)
  - [x] Add checkpoint/CLEAR responsibilities to Implementation roles (LeadDeveloper/CodeReviewer)
  - [x] Inject references to `docs/Context_Management_Guide.md` and checkpoint templates in generated outputs
  - [ ] Include prompt questions that collect checkpoint frequency and target agents for clears
- [x] Wire new templates into generation
  - [x] Include `templates/ROLE_Architect_Planning.md`, `templates/ROLE_ProjectManager_Planning.md`, `templates/ROLE_LeadDeveloper_Implementation.md`, `templates/ROLE_CodeReviewer_Implementation.md`
  - [x] Offer `templates/PROJECT_TASKS_with_checkpoints.md` and `templates/CHECKPOINT_meta_task.md` when generating task artifacts
- [ ] Add tests/fixtures for generator
  - [ ] Verify generated instruction files mention `[[CLEAR]]` usage and post-clear protocol
  - [ ] Verify PROJECT_TASKS templates include checkpoint meta-tasks
- [ ] Update documentation
  - [ ] Note generator support for context management in `docs/Documentation_Guidelines.md` or script help text

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
