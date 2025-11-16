# Session Mapping Guide - Expense_Tracker_CLI

This document explains which instruction files to use for each orchestration session.

---

## Phase 1: Requirements

**Roles:**
- AI 1: `ROLE_ProductManager_Requirements.md` (Lead)
- AI 2: `ROLE_BusinessAnalyst_Requirements.md`

**Command Example:**
```bash
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/projects/Expense_Tracker_CLI/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file templates/projects/Expense_Tracker_CLI/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "[TODO: Add phase-specific prompt]" \
  --max-turns 10 \
  --log-file artifacts/phase1/conversation.log
```

---

## Phase 2: Planning

**Roles:**
- AI 1: `ROLE_EngineeringManager_Planning.md` (Lead)
- AI 2: `ROLE_TechnicalLead_Planning.md`

**Command Example:**
```bash
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/projects/Expense_Tracker_CLI/ROLE_EngineeringManager_Planning.md \
  --ai2-instruction-file templates/projects/Expense_Tracker_CLI/ROLE_TechnicalLead_Planning.md \
  --group-system-prompt "[TODO: Add phase-specific prompt]" \
  --max-turns 10 \
  --log-file artifacts/phase2/conversation.log
```

---

## Phase 3: Implementation

**Roles:**
- AI 1: `ROLE_LeadDeveloper_Implementation.md` (Lead)
- AI 2: `ROLE_CodeReviewer_Implementation.md`

**Command Example:**
```bash
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/projects/Expense_Tracker_CLI/ROLE_LeadDeveloper_Implementation.md \
  --ai2-instruction-file templates/projects/Expense_Tracker_CLI/ROLE_CodeReviewer_Implementation.md \
  --group-system-prompt "[TODO: Add phase-specific prompt]" \
  --max-turns 10 \
  --log-file artifacts/phase3/conversation.log
```

---

