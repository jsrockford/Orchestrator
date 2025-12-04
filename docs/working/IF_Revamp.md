# Instruction File Revamp Plan
**Date**: December 4, 2025
**Status**: Team Approved - Ready for Implementation
**Goal**: Fix critical bugs and redesign Phase 3 collaboration to enable reliable "two pairs of eyes" implementation

**Team Sign-Off**: Codex ✓, Gemini ✓, Claude ✓ (with refinements incorporated)

---

## Executive Summary

Current instruction files are **70% ready** but have critical bugs and architectural gaps that prevent successful two-agent collaboration in Phase 3 (Implementation). This plan addresses:

1. **Parsing bugs** that corrupt generated files (0 tasks, broken tech guidance)
2. **Role confusion** causing "two cooks in one kitchen" problem
3. **Missing choreography** for review handoffs and approvals
4. **Context synchronization** issues causing agent drift

**Expected Outcome**: 90%+ success rate for Phase 3 collaborative implementation with clear division of labor and quality gates.

---

## Phase A: Critical Parsing Bugs (FIX FIRST)

These bugs break the generated instruction files and must be fixed before any testing can succeed.

### A1. Task Count Extraction Bug
**Location**: `scripts/generate_instruction_files.py` - `_parse_project_tasks()` method
**Symptom**: Phase 3 files say "All 0 tasks from PROJECT_TASKS.md are complete" when there are 40+ tasks
**Root Cause**: Parser likely counts top-level tasks only, missing subtasks, or fails to find task markers entirely
**Fix**:
- Update regex pattern to match all task formats: `- [ ]`, `- [x]`, numbered lists
- Count both parent tasks and subtasks
- Return accurate count to populate success criteria template
- Test with Craps2 PROJECT_TASKS.md (should return ~40)

**Validation**: Generated GEMINI-3.md should say "All 40 tasks from PROJECT_TASKS.md are complete"

---

### A2. Technology Guidance Corruption
**Location**: `scripts/generate_instruction_files.py` - `_parse_architecture()` or tech guidance extraction
**Symptom**: "Python-React Technology Guidance" section contains raw TypeScript interface snippets without context
**Root Cause**: Parser extracts code blocks instead of prose, or grabs wrong section of ARCHITECTURE.md
**Fix**:
- Look for proper headings: "## Technology Stack", "## Core Components", "## Tech Stack"
- Extract descriptive text, not code blocks
- If tech stack info is inline/scattered, extract key terms (React, Vite, TypeScript, etc.)
- If extraction fails, fall back to: `<!-- TODO: Add technology-specific guidance for [tech_stack] -->`

**Validation**: Generated files should have readable guidance like "React/Vite/TypeScript project using Context API for state..." OR a TODO comment, NOT raw code snippets.

---

### A3. Working Directory Path Mismatch
**Location**: `scripts/generate_instruction_files.py` - `_customize_template()` method
**Symptom**: Generated files hardcode `/home/dgray/Projects/scratch/Craps2` but actual project is in `/scratch/CrapsTest`
**Root Cause**: Template uses `config.project_path` but this may be the instruction_files output directory, not the actual working directory

**Fix** (with backward compatibility):
- Add `working_directory` field to ProjectConfig (distinct from instruction output path)
- Add optional `--working-dir` CLI argument to generator script
- Implement sourcing with precedence: CLI arg > USER_REQUEST.md > config.project_path (default)
- If USER_REQUEST.md exists and contains "Working Directory: /path", extract from there
- Replace `[PROJECT_DIRECTORY]` placeholder in security boundary section with actual working directory
- Update "**Working Directory:**" line in Project Context section

**Backward Compatibility**: If no CLI arg and no USER_REQUEST.md extraction, default to `config.project_path` (current behavior). This ensures no regression for existing workflows.

**Validation**: Security boundary guidance should show correct path matching where the project code will actually be created.

---

## Phase B: Protocol & Architecture Redesign

Fundamental changes to how LeadDeveloper and CodeReviewer collaborate.

### B1. CodeReviewer State Machine (NEW ARCHITECTURE)
**Location**: `scripts/generate_instruction_files.py` - ROLE_DEFAULTS['CodeReviewer'] + new template section
**Current Problem**: CodeReviewer has mirrored workflow phases (Phase 1-4) identical to LeadDeveloper, causing "two cooks" problem
**New Design**: Replace workflow phases with explicit state machine

**State Machine Definition**:
```markdown
## CodeReviewer State Machine

You operate in one of four states. Transition between states based on signals from LeadDeveloper.

### State 1: MONITORING (Initial State)
**What you do:**
- Read LeadDeveloper's delimited responses passively
- Track which PROJECT_TASKS sections they're working on
- Note when they complete tasks
- Do NOT write code, create files, or implement features
- Respond with brief acknowledgments: "Noted - monitoring Section 1 progress"

**Transition:** When you see `[[REVIEW_REQUEST:section_name]]` → Go to ACTIVE REVIEW

---

### State 2: ACTIVE REVIEW
**What you do:**
- Read all code files mentioned in the review request
- Identify bugs, logic errors, missing edge cases
- Check that PRD requirements are met
- Verify coding standards and best practices
- Prepare defect list OR approval decision

**Transition:** Once analysis complete → Go to TESTING

---

### State 3: TESTING
**What you do:**
- Run test commands (e.g., `npm test`, `python -m pytest`)
- Execute integration tests if applicable
- Verify files exist and have expected content
- Test edge cases manually if needed
- Collect evidence for approval/rejection

**Transition:** Once testing complete → Go to APPROVAL/FEEDBACK

---

### State 4: APPROVAL/FEEDBACK
**What you do:**
- If tests pass and no critical issues: **Provide APPROVAL with evidence**
  - Example: "APPROVED - Ran `npm test`, all 12 tests passing. Verified dice.ts handles edge case of invalid range."
- If issues found: **Provide DEFECT LIST**
  - Example: "DEFECTS FOUND: 1) calculatePayout() doesn't handle Hard 8 bet. 2) Missing unit test for craps (2,3,12) on come-out roll."
- Use evidence-based feedback (reference specific files, line numbers, test results)

**Transition:** After providing approval/feedback → Return to MONITORING

---

### Critical Rules:
- **NEVER implement code while in MONITORING state** - this is LeadDeveloper's responsibility
- **NEVER approve without evidence** - must cite test results or file verification
- **NEVER skip TESTING state** - always run verification before approval
- You may suggest improvements, but approval is binary: APPROVED or DEFECTS FOUND
```

**Implementation**:
- Replace "## Workflow Phases" section in CodeReviewer template with state machine
- Update primary responsibilities to reference states
- Add warnings against hallucinating implementation duties

**Validation**: Generated QWEN-3.md/GEMINI-3.md for CodeReviewer should have state machine, NOT workflow phases.

---

### B2. [[REVIEW_REQUEST]] Signal Protocol (GUIDANCE-ONLY)
**Location**: `scripts/generate_instruction_files.py` - LeadDeveloper template + checkpoint meta-tasks
**Purpose**: Explicit handoff signal when LeadDeveloper wants review

**⚠️ TEAM CONSENSUS: Guidance-only initially, add orchestrator enforcement later if models fail to self-regulate (Gemini)**

**Configuration** (Codex's de-risking suggestion):
Add to `config.yaml`:
```yaml
review_requests:
  blocking: false              # Start as guidance-only (set true to enable orchestrator enforcement)
  timeout_seconds: 300         # If blocking enabled, max wait for review response
```

**Implementation**:

**In LeadDeveloper Instructions**:
```markdown
## Requesting Code Review

After completing each PROJECT_TASKS section:
1. Ensure all code is committed (if git workflow)
2. Self-review for obvious issues
3. Signal review request: `[[REVIEW_REQUEST:section_name]]`
4. Include summary: "Completed Section 1 - Core Game Logic. Implemented dice.ts, payouts.ts, rules.ts with unit tests."
5. Wait for CodeReviewer's approval or defect list before proceeding to next section
```

**In Checkpoint Meta-Tasks** (PROJECT_TASKS.md template):
```markdown
### CHECKPOINT: Core Logic Complete
- Trigger: After finishing Task 1.4
- LeadDeveloper: Emit `[[REVIEW_REQUEST:Section_1_Core_Logic]]` in your delimited response
- CodeReviewer: Transition to ACTIVE REVIEW state, test logic functions, provide approval/defects
- Both: After review complete, emit `[[CHECKPOINT:Logic_Complete]]` for synchronized clear
- Next focus: Section 2 - State Management
```

**Validation**: Generated files should show review request protocol in both LeadDeveloper and CodeReviewer instructions.

---

### B3. Synchronized Checkpoint System (PHASED ROLLOUT)
**Location**: `backend/conversation_manager.py` + checkpoint meta-task templates
**Current Problem**: Only LeadDeveloper clears at checkpoints; CodeReviewer context drifts
**New Design**: System-wide synchronized clears triggered by `[[CHECKPOINT:name]]`

**⚠️ TEAM CONSENSUS: Phased rollout due to complexity (Codex, Gemini)**

**Signal Change**:
- OLD: `[[CLEAR:leaddeveloper]]` (agent-specific)
- NEW: `[[CHECKPOINT:section_name]]` (system-wide)

**Orchestrator Behavior**:
1. Detect `[[CHECKPOINT:section_name]]` in either agent's response
2. Wait for BOTH agents to signal (with timeout handling)
3. Clear context for ALL agents simultaneously
4. Send identical post-clear prompt to both:
   ```
   CHECKPOINT REACHED: Section_1_Core_Logic complete

   Please re-read the following to restore context:
   - PRD.md
   - ARCHITECTURE.md
   - PROJECT_TASKS.md (focus on Section 2)

   LeadDeveloper: Begin Section 2 implementation
   CodeReviewer: Resume MONITORING state for Section 2
   ```

**Timeout Handling** (addressing Gemini's concern):
```python
# In conversation_manager.py
checkpoint_timeout = self.config.get('checkpoints', {}).get('timeout_seconds', 120)
if both_agents_signaled or timeout_exceeded:
    force_clear_both_agents()
    if timeout_exceeded:
        logger.warning(f"Checkpoint {name} forced after {timeout} second timeout")
```

**Configuration** (Codex's de-risking suggestion):
Add to `config.yaml`:
```yaml
checkpoints:
  synchronized: true           # Enable [[CHECKPOINT]] system (set false to use old [[CLEAR:agent]])
  timeout_seconds: 120         # Max wait for both agents to signal
  fallback_to_individual: true # Fall back to [[CLEAR:agent]] on timeout/failure
```

**Implementation Phases**:

**Phase B.3a - Pilot** (ONE section only):
- Implement `[[CHECKPOINT]]` for Section 1: Core Logic only
- Other sections continue using `[[CLEAR:agent]]`
- Test with actual AI run, observe timeout and synchronization behavior

**Phase B.3b - Validation**:
- Review logs from pilot run
- Verify both agents cleared correctly
- Check timeout handling works
- Assess if coordination improves context alignment

**Phase B.3c - Decision Point**:
- **If pilot succeeds**: Roll out `[[CHECKPOINT]]` to all sections
- **If pilot fails**: Revert to paired `[[CLEAR:agent]]` meta-tasks (both agents clear separately on same turn)
- Update config.yaml `checkpoints.synchronized: false` to disable if needed

**Implementation Changes**:

**In `conversation_manager.py`**:
- Add `_detect_checkpoint_signal()` method similar to `_detect_clear_command()`
- Track checkpoint signals per agent: `self._checkpoint_signals = {}`
- Implement timeout tracking with `time.time()` comparisons
- When both agents signal (or timeout), execute synchronized clear
- Set `_resume_speaker` to LeadDeveloper after clear
- Add fallback: if `checkpoints.synchronized: false`, treat `[[CHECKPOINT]]` as regular `[[CLEAR:agent]]`

**In Template Files**:
- Update checkpoint meta-tasks to use `[[CHECKPOINT:name]]` syntax
- Keep individual `[[CLEAR:agent]]` references as comments for fallback option
- Add post-checkpoint focus instructions for both roles

**Validation**:
- Checkpoint meta-tasks should say `[[CHECKPOINT:Logic_Complete]]`, not `[[CLEAR:leaddeveloper]]`
- Both agents should be cleared and receive identical prompts after checkpoint
- Config flag should allow disabling synchronized clears if needed

---

### B4. Evidence-Based Approval Requirements (GUIDANCE-ONLY)
**Location**: CodeReviewer template - State 4 (APPROVAL/FEEDBACK)
**Purpose**: Prevent rubber-stamp reviews

**⚠️ TEAM CONSENSUS: Guidance-only, no orchestrator validation (Gemini - parsing free-text evidence is error-prone)**

**Implementation**:

```markdown
## Evidence Requirements for Approval

Your APPROVAL response MUST include at least TWO of the following types of evidence:

1. **Test Results**: "Ran `npm test` - all 15 tests passing"
2. **File Verification**: "Confirmed files exist: src/logic/dice.ts (127 lines), src/logic/payouts.ts (89 lines)"
3. **Manual Testing**: "Manually tested Field bet with roll of 3 - correctly paid 1:1"
4. **Code Inspection**: "Reviewed calculatePayout() at payouts.ts:45 - handles all 8 bet categories per PRD"
5. **Edge Case Verification**: "Tested boundary: Hard 6 with rolls (3,3) pays 9:1, (2,4) loses - correct"

**Invalid Approvals** (will be rejected):
- "Looks good!"
- "LGTM"
- "Approved" (without evidence)
- "Great work!" (without specific verification)

**Format**:
```
**APPROVAL** - Section 1 Core Logic

Evidence:
1. Ran `npm test` - All 12 unit tests passing (dice.test.ts, payouts.test.ts, rules.test.ts)
2. Verified calculatePayout() handles all bet types from PRD Table 2.1
3. Tested edge case: Pass Line bet on come-out roll of 12 (craps) - correctly loses bet

Proceed to Section 2.
```
```

**Validation**: Generated CodeReviewer files should have evidence requirements in State 4 section.

---

### B5. Escalation Protocol (NEW)
**Location**: Both LeadDeveloper and CodeReviewer templates + `conversation_manager.py`
**Purpose**: Safety valve for critical disagreements that block progress

**⚠️ TEAM CONSENSUS: Add [[ESCALATION]] signal for deadlock situations (Gemini)**

**New Signal**: `[[ESCALATION:reason]]`

**Usage**: Either agent can emit if critical disagreement blocks progress

**Example Scenario**:
```markdown
CodeReviewer: "[[ESCALATION:security_vulnerability]] - Hard disagreement on input validation.
LeadDeveloper believes PRD doesn't require it, but I see SQL injection risk in
database.ts:45. LeadDeveloper has final authority per role definition, but this is
a critical security issue that could compromise user data."

Orchestrator: Detects escalation, pauses discussion, logs detailed context
```

**Orchestrator Behavior**:
```python
# In conversation_manager.py
def _detect_escalation_signal(self, response: str) -> Optional[Dict[str, str]]:
    """Detect [[ESCALATION:reason]] in agent response"""
    pattern = r'\[\[ESCALATION:([^\]]+)\]\]'
    match = re.search(pattern, response)
    if match:
        return {
            'reason': match.group(1),
            'agent': self._current_speaker,
            'turn': self._turn_count
        }
    return None

# On detection:
- Log detailed escalation with full context
- Add WARNING flag to conversation log
- (Future) Send notification to human supervisor
- (For now) Allow discussion to continue with logged warning
- Do NOT auto-terminate discussion
```

**In Both Role Templates**:
```markdown
## Escalation Protocol

**When to escalate:**
- Critical security vulnerability disagreement
- Data loss or corruption risk
- PRD interpretation deadlock after 2 exchanges
- Fundamental architecture disagreement blocking progress

**How to escalate:**
Emit `[[ESCALATION:brief_reason]]` and explain the issue:
```
[[ESCALATION:security_risk]]

I believe the current implementation of user authentication (auth.ts:89) has a
critical SQL injection vulnerability. LeadDeveloper disagrees, citing that PRD
doesn't specify input sanitization. However, this is a security best practice
that should override the PRD silence on this matter.

Specific issue: Line 89 uses string concatenation for SQL query with user input.
Recommended fix: Use parameterized queries.
```

**After escalation:**
- Discussion continues (orchestrator logs but doesn't halt)
- Consider documenting the decision in code comments or README
- LeadDeveloper retains final authority per role definition
- CodeReviewer may withhold [[PROJECT_COMPLETE]] approval if issue remains
```

**Configuration** (optional):
```yaml
escalation:
  enabled: true
  log_level: WARNING
  notify_human: false  # Future feature - email/slack notification
  pause_discussion: false  # If true, require human input to continue
```

**Validation**:
- Both role templates should have escalation protocol section
- conversation_manager.py should detect and log `[[ESCALATION:...]]` signals
- Config should have escalation settings with sensible defaults

---

## Phase C: Refinement & Polish

### C1. Task Ownership Assignment (WITH PREFIX PRESERVATION)
**Location**: Template for PROJECT_TASKS.md generation + refinement script
**Purpose**: Eliminate ambiguity about who does what

**⚠️ CODEX CAUTION: Ensure generator doesn't overwrite existing TASKS content unexpectedly and refinement doesn't strip markers**

**Implementation**:

Add ownership prefixes to tasks:
- `[LEAD]` - LeadDeveloper implements
- `[REVIEW]` - CodeReviewer verifies/tests
- `[BOTH]` - Collaborative (e.g., project setup)

**Example**:
```markdown
## Section 1: Core Game Logic
- [ ] [LEAD] **Task 1.1**: Dice Logic - Implement rollDice() in src/logic/dice.ts
- [ ] [LEAD] **Task 1.2**: Write unit tests for dice.ts
- [ ] [REVIEW] **Task 1.2a**: Verify dice tests cover edge cases (range validation, randomness)
- [ ] [LEAD] **Task 1.3**: Payout Calculation Engine - Implement calculatePayout()
- [ ] [REVIEW] **Task 1.3a**: Test all 8 bet categories against PRD Table 2.1
```

**Special Cases**:
- `[BOTH] Task 0.1: Initialize Project` - Lead scaffolds, Review verifies structure
- `[BOTH] Task 5.3: Final QA` - Both participate in testing

**Prefix Preservation** (critical for refinement script):
```python
# When updating existing PROJECT_TASKS.md
task_pattern = r'^(\s*-\s*\[.\]\s*)(\[LEAD\]|\[REVIEW\]|\[BOTH\])?\s*(.+)$'

# If prefix exists, preserve it:
if existing_prefix:
    keep_existing_prefix()  # User may have hand-edited
# If no prefix and initial generation:
    add_prefix_based_on_task_type()
# If refinement and no prefix:
    dont_add_prefix()  # Respect user's choice to omit
```

**Generation Strategy**:
- **Initial creation**: Add prefixes to all tasks
- **Refinement**: Preserve existing prefixes, don't add new ones to unprefixed tasks
- **Rationale**: User may have intentionally removed prefixes or hand-edited tasks

**Validation**:
- Generated PROJECT_TASKS.md should have ownership prefixes on all tasks (initial creation)
- Refined PROJECT_TASKS.md should preserve existing prefixes (no stripping)

---

### C2. File Creation Protocol
**Location**: LeadDeveloper template - Primary Responsibilities
**Purpose**: Clarify who creates files vs who reviews them
**Implementation**:

```markdown
## File Creation Responsibilities

**LeadDeveloper Creates:**
- All source code files (src/**/*)
- Unit test files (**/tests/*, **/*.test.ts)
- Configuration files (package.json, tsconfig.json, vite.config.ts)
- Initial documentation (README.md)

**CodeReviewer Creates:**
- Integration test files (tests/integration/*)
- Test reports or verification logs
- Bug reports (if defects found)

**Both Collaborate On:**
- README.md (Lead drafts, Review verifies accuracy)
- Final documentation

**Protocol:**
- LeadDeveloper: Create files, implement features, write unit tests
- CodeReviewer: DO NOT create source files unless explicitly fixing a bug after approval
- CodeReviewer: MAY create integration tests, verification scripts, or test documentation
```

**Validation**: Generated files should clearly state LeadDeveloper creates source files, CodeReviewer creates integration tests only.

---

### C3. Conflict Resolution Process
**Location**: Both LeadDeveloper and CodeReviewer templates - Collaboration Protocols section
**Purpose**: Handle disagreements without stalling project
**Implementation**:

```markdown
## Conflict Resolution Protocol

**When CodeReviewer identifies a defect:**
1. CodeReviewer provides specific defect with evidence and suggested fix
2. LeadDeveloper responds with either:
   - Agreement: "Fixed in commit abc123" OR "Will fix in next turn"
   - Disagreement: "This is correct because [reasoning with PRD reference]"

**If disagreement persists after one exchange:**
1. LeadDeveloper documents the decision in code comments or README
2. Both note the disagreement in their responses
3. Proceed with LeadDeveloper's implementation (Lead has final say per role authority)
4. CodeReviewer may withhold final [[PROJECT_COMPLETE]] approval if disagreement is critical

**Example**:
```
CodeReviewer: "DEFECT: Hard 6 should pay 9:1, not 7:1 per PRD Table 2.2"
LeadDeveloper: "You're right - fixed in payouts.ts:67"
[Continue normally]

---OR---

CodeReviewer: "DEFECT: Should validate bet minimum before accepting"
LeadDeveloper: "PRD doesn't require validation - that's a UI concern for future phase"
CodeReviewer: "Noted - documenting as future enhancement. Approved for current phase."
[Continue normally]
```

**Critical Issues**: If CodeReviewer finds a critical bug (security, data loss, PRD violation) and LeadDeveloper disagrees, CodeReviewer may escalate by withholding [[PROJECT_COMPLETE]] approval.
```

**Validation**: Both role files should have identical conflict resolution process.

---

### C4. Testing Division of Labor
**Location**: Both templates - Secondary Responsibilities
**Purpose**: Clarify who writes which tests
**Implementation**:

**In LeadDeveloper Template**:
```markdown
## Testing Responsibilities

**You Write:**
- Unit tests for each module/function you implement
- Component tests for UI elements
- Test coverage goal: 80%+ of your code

**Format**: Co-locate tests with code (dice.test.ts next to dice.ts) or use /tests directory per project conventions

**Before Review Request**: Run all tests and ensure they pass
```

**In CodeReviewer Template**:
```markdown
## Testing Responsibilities

**You Write:**
- Integration tests (cross-module workflows)
- End-to-end tests (full user scenarios)
- Regression tests (if bugs are found and fixed)

**You Verify:**
- LeadDeveloper's unit tests exist and are comprehensive
- Tests actually test the right behavior (not just coverage theater)
- Edge cases are covered

**You Run:**
- All existing tests before approval
- Your own integration/e2e tests
- Manual testing for critical workflows
```

**Validation**: Both files should have complementary testing responsibilities.

---

### C5. Progress Tracking Mechanism
**Location**: Both templates - new section
**Purpose**: Help agents track what's done without re-reading everything
**Implementation**:

```markdown
## Progress Tracking

**Method**: Maintain a running checklist in your delimited responses

**Format**:
```
**Progress Update**
✅ Section 0: Foundations (Tasks 0.1-0.3 complete)
✅ Section 1: Core Logic (Tasks 1.1-1.4 complete, APPROVED by CodeReviewer)
🔄 Section 2: State Management (Task 2.1 complete, Tasks 2.2-2.3 in progress)
⏳ Section 3: UI (Not started)
⏳ Section 4: Gameplay (Not started)
⏳ Section 5: Persistence (Not started)
```

**Update this checklist in each response** so both you and your teammate can quickly assess progress.
```

**Validation**: Both role files should have progress tracking guidance.

---

### C6. Review Request Format Standardization
**Location**: LeadDeveloper template + checkpoint examples
**Purpose**: Consistent format for review requests
**Implementation**:

```markdown
## Review Request Format

When emitting `[[REVIEW_REQUEST:section_name]]`, use this format:

```
**[[REVIEW_REQUEST:Section_1_Core_Logic]]**

**Scope**: Tasks 1.1 through 1.4 (Core Game Logic - Pure Functions)

**Files Changed**:
- src/logic/dice.ts (42 lines) - rollDice() implementation
- src/logic/dice.test.ts (38 lines) - unit tests
- src/logic/payouts.ts (127 lines) - calculatePayout() for all bet types
- src/logic/payouts.test.ts (215 lines) - comprehensive payout tests
- src/logic/rules.ts (34 lines) - constants and helpers

**Testing**:
- All unit tests passing (npm test)
- Manually verified Pass Line, Field, and Hard 4 bets

**Known Issues**: None

**Ready for review.**
```

This structured format helps CodeReviewer quickly understand what to review.
```

**Validation**: LeadDeveloper template should have review request format example.

---

## Implementation Sequence

### Step 1: Fix Parsing Bugs (Phase A) - PRIORITY
**File**: `scripts/generate_instruction_files.py`
**Status**: MUST FIX FIRST - blocks all testing

1. **A1 - Task Counting**: Fix `_parse_project_tasks()` to count all tasks correctly
2. **A2 - Tech Guidance**: Fix extraction to produce readable prose or TODO, not code snippets
3. **A3 - Working Directory**: Add CLI arg, USER_REQUEST.md extraction, with backward-compatible precedence
4. Test generation with Craps2 - verify all fixes

**Success Criteria**: Generate instruction files for Craps2, confirm:
- "All 40 tasks" (not "All 0 tasks")
- Readable tech guidance or TODO (not corrupted snippets)
- Correct working directory in security boundary

---

### Step 2: Implement Protocol Changes (Phase B) - ARCHITECTURAL
**Files**: `scripts/generate_instruction_files.py`, `backend/conversation_manager.py`, `config.yaml`

**B1 - CodeReviewer State Machine** (Full implementation):
1. Create new template section with 4-state machine (Monitoring → Active Review → Testing → Approval)
2. Update ROLE_DEFAULTS['CodeReviewer'] primary responsibilities to reference states
3. Remove mirrored workflow phases from CodeReviewer template
4. Add "DO NOT implement code" warnings in Monitoring state
5. Test generation - verify state machine appears in QWEN-3.md, NOT workflow phases

**B2 - Review Request Protocol** (Guidance-only, no enforcement):
1. Add review request guidance to LeadDeveloper template with format example
2. Add config section `review_requests.blocking: false`
3. Update checkpoint meta-tasks to include `[[REVIEW_REQUEST:section]]` signals
4. Add review request protocol to CodeReviewer template (state transition trigger)
5. Test generation - verify protocol appears in both files

**B3 - Synchronized Checkpoints** (PHASED ROLLOUT):

**B3a - Pilot** (ONE section only):
1. Add config section `checkpoints.synchronized: true` with timeout settings
2. Add `_detect_checkpoint_signal()` to conversation_manager.py
3. Implement synchronized clear logic with timeout handling
4. Track checkpoint signals per agent: `self._checkpoint_signals = {}`
5. Update checkpoint meta-task template for Section 1 ONLY to use `[[CHECKPOINT:Logic_Complete]]`
6. Other sections keep `[[CLEAR:agent]]` for now
7. Set `_resume_speaker` to LeadDeveloper after synchronized clear

**B3b - Validation**:
1. Test with actual AI run on Craps2 Phase 3 (Section 1)
2. Review logs - verify both agents cleared at same time
3. Check timeout handling if one agent fails to signal
4. Assess context alignment improvement

**B3c - Decision Point**:
- **Success**: Roll out `[[CHECKPOINT]]` to all sections
- **Failure**: Revert to paired `[[CLEAR:agent]]` meta-tasks, set `checkpoints.synchronized: false`

**B4 - Evidence-Based Approval** (Guidance-only, no validation):
1. Add evidence requirements section to CodeReviewer State 4 template
2. Provide examples of valid approvals (with 2+ evidence types)
3. Provide examples of invalid approvals ("LGTM", "Looks good!")
4. Test generation - verify evidence section present

**B5 - Escalation Protocol** (NEW):
1. Add config section `escalation.enabled: true` with log settings
2. Add `_detect_escalation_signal()` to conversation_manager.py
3. Log escalations with WARNING level, full context
4. Add escalation protocol section to BOTH LeadDeveloper and CodeReviewer templates
5. Document when to escalate, how to format, what happens after
6. Test generation - verify escalation section in both files

**Success Criteria**:
- Generate instruction files, verify all protocol changes present
- Config.yaml has new sections: `checkpoints`, `review_requests`, `escalation`
- Run pytest tests/test_context_management_clear.py - verify synchronized clears work (pilot only)
- Pilot checkpoint succeeds OR gracefully falls back to individual clears

---

### Step 3: Add Refinements (Phase C) - POLISH
**Files**: `scripts/generate_instruction_files.py`, refinement script, template files

1. **C1 - Task Ownership** (with prefix preservation):
   - Add `[LEAD]`, `[REVIEW]`, `[BOTH]` prefixes to PROJECT_TASKS.md template
   - Update refinement script to preserve existing prefixes (don't strip or overwrite)

2. **C2 - File Creation Protocol**: Add to LeadDeveloper and CodeReviewer templates

3. **C3 - Conflict Resolution**: Add to collaboration protocols section in both templates

4. **C4 - Testing Division**: Add to both templates' secondary responsibilities

5. **C5 - Progress Tracking**: Add new section to both templates with checklist format

6. **C6 - Review Request Format**: Add standardized format example to LeadDeveloper template

**Success Criteria**: Generate complete instruction files, verify all sections present and coherent

---

### Step 4: End-to-End Testing
1. Generate fresh instruction files for Craps2 project
2. Manually review all 6 role files (Phase 1, 2, 3 for both roles)
3. Run Phase 3 simulation with actual AI models
4. Observe collaboration quality, identify any remaining gaps

**Success Criteria**:
- No parsing errors in generated files
- Clear role separation in Phase 3
- Review handoffs work smoothly
- Both agents signal completion appropriately

---

## Success Metrics

**Current State**: 70% ready - significant bugs and role confusion
**Target State**: 90%+ ready - clear collaboration with quality gates

**Key Improvements**:
1. ✅ Parsing bugs eliminated (files generate correctly)
2. ✅ Role confusion eliminated (state machine prevents "two cooks")
3. ✅ Review choreography explicit (review request → test → approve/defect)
4. ✅ Context synchronization enforced (paired clears at checkpoints)
5. ✅ Quality gates enforced (evidence-based approvals)

**Risk Mitigation**:
- **"Two cooks" problem**: SOLVED by state machine (LeadDev implements, CodeReviewer reviews)
- **"Rubber stamp" reviews**: SOLVED by evidence requirements
- **Context drift**: SOLVED by synchronized checkpoints
- **Ownership ambiguity**: SOLVED by task prefixes and file creation protocol
- **Stalled conflicts**: SOLVED by conflict resolution process with LeadDev final authority

---

## Team Consensus Answers (RESOLVED)

All open questions have been resolved through team review:

| Question | Decision | Rationale |
|----------|----------|-----------|
| **1. Checkpoint Syntax** | `[[CHECKPOINT:name]]` ✓ | More semantic than `[[SYNC_CLEAR:name]]` (Gemini) |
| **2. Review Request Blocking** | Guidance-only initially | Add enforcement later if models fail to self-regulate (Gemini) |
| **3. Evidence Validation** | Trust AI, no parsing | Parsing free-text evidence is error-prone (Gemini) |
| **4. Task Ownership Enforcement** | Guidance-only | Keep orchestrator lightweight (Gemini) |
| **5. State Machine Transitions** | Agent self-management | Keep orchestrator lightweight (Gemini) |
| **6. Escalation Signal** | Yes, add `[[ESCALATION]]` ✓ | Safety valve for deadlocks (Gemini) |

**Implementation Approach**: Start with guidance-only (lightweight orchestrator), add enforcement later if models demonstrate they can't self-regulate. Use configuration flags (`checkpoints.synchronized`, `review_requests.blocking`) to enable features gradually.

---

## Rollback Plan

If implementation causes regressions:

1. **Phase A failures**: Revert parsing changes, use manual TODO filling as workaround
2. **Phase B failures**: Keep state machine in CodeReviewer template, but disable synchronized clears and revert to `[[CLEAR:agent]]`
3. **Phase C failures**: These are guidance additions - can be removed without affecting core functionality

**Git Strategy**: Create feature branch `feature/if-revamp`, commit each phase separately for easy revert.

---

## Next Steps - READY TO IMPLEMENT

**Team Sign-Off Complete**: ✅ Codex ✅ Gemini ✅ Claude

1. ✅ **Team reviewed plan** - All signed off with refinements incorporated
2. ✅ **Don approved approach** - Confirmed to proceed with implementation
3. **🔄 BEGIN IMPLEMENTATION**: Claude starts with Phase A (parsing bug fixes)
4. **Test Phase A** - Verify generated files look correct
5. **Claude implements Phase B** - Protocol changes (state machine, checkpoints, escalation)
6. **Test Phase B** - Run pytest and pilot checkpoint with Craps2
7. **Claude implements Phase C** - Refinements (task ownership, protocols, tracking)
8. **End-to-end test** - Full Craps2 Phase 3 run with AI models
9. **Iterate based on results** - Adjust as needed

---

**Status**: APPROVED - Ready to begin Phase A implementation
