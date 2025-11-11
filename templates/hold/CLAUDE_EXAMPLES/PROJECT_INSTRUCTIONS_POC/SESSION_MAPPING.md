# Session to Role Mapping Guide

This document maps which ROLE instruction files to use for each orchestration session.

---

## Session 1: Requirements & PRD Creation

**Phase**: Requirements Discovery
**Goal**: Convert user request into comprehensive Product Requirements Document (PRD)
**Completion Signal**: `[[PROJECT_COMPLETE]]` when PRD is ready

### Team Composition (2 AIs)

| Model/Agent | Role File | Responsibilities |
|-------------|-----------|------------------|
| **AI 1** | `ROLE_ProductManager_Requirements.md` | User perspective, problem definition, scope, priorities |
| **AI 2** | `ROLE_BusinessAnalyst_Requirements.md` | Technical details, calculations, validation rules, edge cases |

### Input Files
- `USER_REQUEST.md` (initial stakeholder description)
- `USER_RESPONSE.md` (if iterating after clarification request)

### Output Files
- `PRD.md` (Product Requirements Document) - **[PRIMARY OUTPUT]**
- OR `CLARIFICATION_REQUEST.md` (if need more info from stakeholder)

### Example Command
```bash
orchestrator \
  --session-name "requirements-session" \
  --ai1-role ROLE_ProductManager_Requirements.md \
  --ai2-role ROLE_BusinessAnalyst_Requirements.md \
  --input-files USER_REQUEST.md \
  --output-dir ./artifacts/session1/ \
  --max-turns 10
```

### Session Success Criteria
- [ ] Both AIs agree on `[[PROJECT_COMPLETE]]`
- [ ] `PRD.md` exists with all required sections
- [ ] All critical requirements defined
- [ ] Edge cases identified
- [ ] Assumptions documented

---

## Session 2: Implementation Planning

**Phase**: Task Decomposition & Technical Design
**Goal**: Break PRD into actionable task list with technical decisions
**Completion Signal**: `[[PROJECT_COMPLETE]]` when plan is ready

### Team Composition (2 AIs)

| Model/Agent | Role File | Responsibilities |
|-------------|-----------|------------------|
| **AI 1** | `ROLE_EngineeringManager_Planning.md` | Task breakdown, dependencies, timeline, milestones |
| **AI 2** | `ROLE_TechnicalLead_Planning.md` | Technology stack, architecture, technical decisions |

### Input Files
- `PRD.md` (from Session 1)

### Output Files
- `TASKS.md` (Detailed task list with dependencies) - **[PRIMARY OUTPUT]**
- `TECH_DECISIONS.md` (Technology choices and rationale) - **[PRIMARY OUTPUT]**
- `PLAN.md` (Optional: Implementation plan with milestones)

### Example Command
```bash
orchestrator \
  --session-name "planning-session" \
  --ai1-role ROLE_EngineeringManager_Planning.md \
  --ai2-role ROLE_TechnicalLead_Planning.md \
  --input-files ./artifacts/session1/PRD.md \
  --output-dir ./artifacts/session2/ \
  --max-turns 10
```

### Session Success Criteria
- [ ] Both AIs agree on `[[PROJECT_COMPLETE]]`
- [ ] `TASKS.md` exists with complete task breakdown
- [ ] All PRD requirements covered by tasks
- [ ] Dependencies clearly mapped
- [ ] Technology stack decided and documented
- [ ] Timeline is realistic

---

## Session 3: Implementation

**Phase**: Code Development & Review
**Goal**: Build working software according to plan
**Completion Signal**: `[[PROJECT_COMPLETE]]` when code is complete and approved

### Team Composition (2 AIs minimum)

| Model/Agent | Role File | Responsibilities |
|-------------|-----------|------------------|
| **AI 1** | `ROLE_LeadDeveloper_Implementation.md` | Write code, implement features, create tests |
| **AI 2** | `ROLE_CodeReviewer_Implementation.md` | Review code, find bugs, verify quality |

**Optional 3rd AI:**
| Model/Agent | Role File | Responsibilities |
|-------------|-----------|------------------|
| **AI 3** | `GAMEDEV_QA_AGENTS.md` (from game dev templates) | Test execution, validation, bug reporting |

### Input Files
- `PRD.md` (from Session 1)
- `TASKS.md` (from Session 2)
- `TECH_DECISIONS.md` (from Session 2)

### Output Files
- `balance_transfer_calc.py` (or main implementation file) - **[PRIMARY OUTPUT]**
- `test_balance_transfer.py` (test file) - **[PRIMARY OUTPUT]**
- `README.md` (usage documentation) - **[PRIMARY OUTPUT]**
- `CODE_REVIEW.md` (optional: review findings)

### Example Command
```bash
orchestrator \
  --session-name "implementation-session" \
  --ai1-role ROLE_LeadDeveloper_Implementation.md \
  --ai2-role ROLE_CodeReviewer_Implementation.md \
  --input-files ./artifacts/session1/PRD.md,./artifacts/session2/TASKS.md,./artifacts/session2/TECH_DECISIONS.md \
  --working-dir ./src/ \
  --output-dir ./artifacts/session3/ \
  --max-turns 20
```

### Session Success Criteria
- [ ] Both AIs agree on `[[PROJECT_COMPLETE]]`
- [ ] All code files created and functional
- [ ] All tests passing
- [ ] Code Reviewer approves (no critical bugs)
- [ ] All PRD acceptance criteria met
- [ ] Documentation complete

---

## Quick Reference Table

| Session | Phase | AI 1 Role | AI 2 Role | AI 3 Role (Optional) | Input | Output |
|---------|-------|-----------|-----------|---------------------|-------|--------|
| **1** | Requirements | ProductManager | BusinessAnalyst | - | USER_REQUEST.md | PRD.md |
| **2** | Planning | EngineeringManager | TechnicalLead | - | PRD.md | TASKS.md, TECH_DECISIONS.md |
| **3** | Implementation | LeadDeveloper | CodeReviewer | QA Engineer | PRD.md, TASKS.md, TECH_DECISIONS.md | code, tests, README |

---

## Orchestrator Configuration Examples

### Option A: Separate Session Commands

Run each session manually, reviewing outputs between sessions:

```bash
# Session 1: Requirements
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create a comprehensive PRD" \
  --max-turns 10 \
  --log-file artifacts/session1/conversation.log

# [Human reviews PRD.md]

# Session 2: Planning
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/ROLE_EngineeringManager_Planning.md \
  --ai2-instruction-file templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/ROLE_TechnicalLead_Planning.md \
  --group-system-prompt "Read PRD.md and create implementation plan" \
  --max-turns 10 \
  --log-file artifacts/session2/conversation.log

# [Human reviews TASKS.md and TECH_DECISIONS.md]

# Session 3: Implementation
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/ROLE_LeadDeveloper_Implementation.md \
  --ai2-instruction-file templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/ROLE_CodeReviewer_Implementation.md \
  --group-system-prompt "Read PRD.md, TASKS.md, TECH_DECISIONS.md and implement the calculator" \
  --max-turns 20 \
  --log-file artifacts/session3/conversation.log
```

### Option B: Chained Sessions (Future Enhancement)

Automatically chain sessions based on completion signals:

```bash
# Future orchestrator feature
python run_multi_session.py \
  --config multi_session_config.yaml \
  --initial-input USER_REQUEST.md \
  --output-dir ./artifacts/
```

Where `multi_session_config.yaml` contains:
```yaml
sessions:
  - name: requirements
    roles:
      - ROLE_ProductManager_Requirements.md
      - ROLE_BusinessAnalyst_Requirements.md
    max_turns: 10
    output_artifacts: [PRD.md]

  - name: planning
    roles:
      - ROLE_EngineeringManager_Planning.md
      - ROLE_TechnicalLead_Planning.md
    max_turns: 10
    input_from_session: requirements
    output_artifacts: [TASKS.md, TECH_DECISIONS.md]

  - name: implementation
    roles:
      - ROLE_LeadDeveloper_Implementation.md
      - ROLE_CodeReviewer_Implementation.md
    max_turns: 20
    input_from_sessions: [requirements, planning]
    output_artifacts: [*.py, README.md]
```

---

## Role Assignment by AI Model Type

### Recommended Assignments

**For Claude Code (best at implementation):**
- Session 1: BusinessAnalyst (technical details)
- Session 2: TechnicalLead (architecture, tech decisions)
- Session 3: LeadDeveloper (code implementation)

**For Gemini (good at analysis and review):**
- Session 1: ProductManager (requirements, scope)
- Session 2: EngineeringManager (planning, dependencies)
- Session 3: CodeReviewer (quality assurance)

**For Qwen (flexible):**
- Session 1: Either role
- Session 2: Either role
- Session 3: Either role or QA Engineer

**For Codex/Aider (code-focused):**
- Session 1: BusinessAnalyst (technical specs)
- Session 2: TechnicalLead (technical decisions)
- Session 3: LeadDeveloper (code implementation)

---

## Troubleshooting

### Session 1 Issues

**Problem**: AIs can't agree whether to request clarification
**Solution**: Add explicit instruction in group-system-prompt:
```
"If either of you identifies critical ambiguities, request clarification.
If both agree you have enough info, proceed with PRD."
```

**Problem**: PRD is too vague
**Solution**: Increase max-turns to allow more discussion (15-20 turns)

### Session 2 Issues

**Problem**: Tasks are too broad or too granular
**Solution**: Check TASKS.md template examples, add explicit guidance in group-system-prompt

**Problem**: Technical decisions lack rationale
**Solution**: Ensure TechnicalLead reads the template section on decision documentation

### Session 3 Issues

**Problem**: Code Reviewer approves without thorough review
**Solution**: Emphasize in group-system-prompt: "Code Reviewer must find at least one issue or provide detailed evidence of correctness"

**Problem**: Developer and Reviewer disagree endlessly
**Solution**: Add turn limit for debate: "If disagreement persists for 3+ turns, escalate to human"

---

## File Location Reference

All role files are located in:
```
/home/dgray/Projects/Orchestrator/templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/
```

**Session 1 Files:**
- `ROLE_ProductManager_Requirements.md`
- `ROLE_BusinessAnalyst_Requirements.md`

**Session 2 Files:**
- `ROLE_EngineeringManager_Planning.md`
- `ROLE_TechnicalLead_Planning.md`

**Session 3 Files:**
- `ROLE_LeadDeveloper_Implementation.md`
- `ROLE_CodeReviewer_Implementation.md`

**Example Input:**
- `USER_REQUEST.md`

**Documentation:**
- `README.md`
- `SESSION_MAPPING.md` (this file)
