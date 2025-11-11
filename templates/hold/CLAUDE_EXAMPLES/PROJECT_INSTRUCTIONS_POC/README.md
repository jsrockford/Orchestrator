# Multi-Session Development Lifecycle POC

This directory contains role-based instruction templates for orchestrating a complete software development lifecycle across three separate sessions.

## Overview

This proof-of-concept demonstrates a multi-session workflow where different teams handle different phases of development:

1. **Session 1 (Requirements)**: Product Manager + Business Analyst create PRD
2. **Session 2 (Planning)**: Engineering Manager + Technical Lead create implementation plan
3. **Session 3 (Implementation)**: Lead Developer + Code Reviewer build the software

## Test Project: Credit Card Balance Transfer Calculator

A financial calculator that helps users decide whether to transfer credit card debt to a 0% promotional card or pay off their current card.

## Files in This Directory

### Role Templates (6 files)

**Session 1 - Requirements Phase:**
- `ROLE_ProductManager_Requirements.md` - User-focused requirements gathering
- `ROLE_BusinessAnalyst_Requirements.md` - Technical requirements specification

**Session 2 - Planning Phase:**
- `ROLE_EngineeringManager_Planning.md` - Task decomposition and project planning
- `ROLE_TechnicalLead_Planning.md` - Technology decisions and architecture

**Session 3 - Implementation Phase:**
- `ROLE_LeadDeveloper_Implementation.md` - Code implementation
- `ROLE_CodeReviewer_Implementation.md` - Code review and quality assurance

### Input File

- `USER_REQUEST.md` - Example stakeholder input describing the credit card calculator problem

## How to Use

### Session 1: Requirements (Create PRD)

**Goal**: Convert user request into comprehensive Product Requirements Document

**Team**: Product Manager + Business Analyst

**Input**: `USER_REQUEST.md`

**Expected Output**: `PRD.md` (or `CLARIFICATION_REQUEST.md` if more info needed)

**Command** (conceptual):
```bash
orchestrator --session requirements \
  --roles ProductManager,BusinessAnalyst \
  --input USER_REQUEST.md \
  --role-files ROLE_ProductManager_Requirements.md,ROLE_BusinessAnalyst_Requirements.md \
  --output-dir ./session1/ \
  --max-turns 10
```

**Completion Signal**: Both AIs signal `[[PROJECT_COMPLETE]]` when PRD is ready

**If Clarification Needed**:
1. AIs produce `CLARIFICATION_REQUEST.md` explaining what they need to know
2. Human creates `USER_RESPONSE.md` with answers
3. Run session again with both files as input
4. Repeat until `[[PROJECT_COMPLETE]]` signaled

---

### Session 2: Planning (Create Task List)

**Goal**: Break PRD into actionable implementation plan

**Team**: Engineering Manager + Technical Lead

**Input**: `PRD.md` (from Session 1)

**Expected Output**:
- `TASKS.md` - Detailed task breakdown with dependencies
- `TECH_DECISIONS.md` - Technology stack and architecture decisions

**Command** (conceptual):
```bash
orchestrator --session planning \
  --roles EngineeringManager,TechnicalLead \
  --input PRD.md \
  --role-files ROLE_EngineeringManager_Planning.md,ROLE_TechnicalLead_Planning.md \
  --output-dir ./session2/ \
  --max-turns 10
```

**Completion Signal**: Both AIs signal `[[PROJECT_COMPLETE]]` when plan is ready

---

### Session 3: Implementation (Build the Software)

**Goal**: Implement the calculator according to plan

**Team**: Lead Developer + Code Reviewer

**Input**:
- `PRD.md` (from Session 1)
- `TASKS.md` (from Session 2)
- `TECH_DECISIONS.md` (from Session 2)

**Expected Output**:
- `balance_transfer_calc.py` - Working calculator code
- `test_balance_transfer.py` - Comprehensive tests
- `README.md` - Usage documentation

**Command** (conceptual):
```bash
orchestrator --session implementation \
  --roles LeadDeveloper,CodeReviewer \
  --input PRD.md,TASKS.md,TECH_DECISIONS.md \
  --role-files ROLE_LeadDeveloper_Implementation.md,ROLE_CodeReviewer_Implementation.md \
  --working-dir ./src/ \
  --max-turns 20
```

**Completion Signal**: Both AIs signal `[[PROJECT_COMPLETE]]` when code is complete and approved

---

## Key Features of These Templates

### 1. Iterative Clarification (Session 1)
- Product team can request clarification if requirements are ambiguous
- Supports multiple rounds of Q&A with stakeholder
- No guessing on critical decisions

### 2. Phased Workflow
- Clear handoffs between sessions via artifacts (PRD → TASKS → Code)
- Each session has focused scope and deliverables
- Can re-run individual sessions if needed

### 3. Role-Specific Guidance
- Each role has clear responsibilities and decision authority
- Templates include best practices for that role
- Common pitfalls are highlighted

### 4. Financial Calculation Focus
- Emphasizes precision (Decimal vs float)
- Requires mathematical verification
- Includes edge case handling

### 5. Quality Gates
- Code must pass review before completion
- Requirements must be testable
- All critical issues must be resolved

## Expected Workflow Timeline

**Session 1 (Requirements)**:
- Single iteration: 6-10 turns
- With clarifications: 10-15 turns total (across iterations)

**Session 2 (Planning)**:
- 8-12 turns

**Session 3 (Implementation)**:
- Initial implementation: 10-15 turns
- With bug fixes: 15-20 turns total

**Total**: 30-45 turns across all three sessions

## Customization Guide

### For Different Projects

To adapt these templates for other projects:

1. **Update USER_REQUEST.md** with your project description
2. **Modify project-specific sections** in templates:
   - Change calculation examples to match your domain
   - Update edge cases to match your requirements
   - Adjust code organization guidance

3. **Keep core structure** intact:
   - Response delimiter protocol
   - Workflow phases
   - Collaboration protocols
   - Quality standards

### For Different Team Sizes

**Single AI (Solo Mode)**:
- Use Product Manager template only for Session 1
- Use Engineering Manager template only for Session 2
- Use Lead Developer template only for Session 3

**Larger Teams (4+ AIs)**:
- Add Test Engineer role (Session 3)
- Add Documentation Specialist (Session 3)
- Add Security Auditor (if needed)

## Testing the POC

### Minimal Test
1. Run Session 1 with `USER_REQUEST.md`
2. Verify PRD is generated
3. Manually review PRD quality

### Full Test
1. Run all three sessions sequentially
2. Verify each session produces expected artifacts
3. Run the final calculator code to verify it works
4. Check if results are mathematically correct

### Success Criteria
- ✅ Session 1 produces complete PRD without human intervention (or clear clarification requests)
- ✅ Session 2 produces actionable task list
- ✅ Session 3 produces working, tested code
- ✅ Final calculator gives correct results
- ✅ All three sessions complete in <45 turns total

## Notes

- These templates assume the orchestrator supports `[[PROJECT_COMPLETE]]` as a completion signal
- Templates include mandatory protocol prepended (security boundaries, response delimiters)
- All templates emphasize not re-reading files unnecessarily
- Communication between AIs happens only through response delimiters

## Future Enhancements

Potential additions to these templates:

1. **Additional roles**: Test Engineer, Documentation Specialist, Security Auditor
2. **Additional phases**: Integration Testing, Deployment, Post-Release Review
3. **Additional project types**: Web apps, games, APIs, CLI tools
4. **Enhanced artifacts**: Architecture diagrams, API specs, deployment plans
5. **Automated hand-offs**: Orchestrator automatically chains sessions based on completion signals

## Questions or Issues

If the templates produce unexpected results:

1. **Check turn count** - May need more turns for complex discussions
2. **Review delimiters** - Ensure AIs are using response delimiters correctly
3. **Check artifacts** - Verify input files are in expected format
4. **Review completion signals** - Ensure both AIs signal before ending session
5. **Adjust max_turns** - Some phases may need more discussion time

---

**Author**: Claude (Orchestrator Development Team)
**Date**: 2025-11-09
**Version**: 1.0 (POC)
