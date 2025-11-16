# Session Mapping - Universal PRD Creation

This document provides command examples and workflow guidance for using the universal PRD creation templates.

---

## Quick Start

**Before you start:**
1. Create `USER_REQUEST.md` in your project directory
2. Replace `[PROJECT_DIRECTORY]` in both role files with your actual path
3. Run the command below

**Single Command:**
```bash
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/prd_universal/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file templates/prd_universal/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create comprehensive PRD.md. If critical information is missing, create CLARIFICATION_REQUEST.md instead." \
  --max-turns 15 \
  --log-file artifacts/prd_session/conversation.log
```

---

## Session Configuration

### Roles

| AI | Role File | Responsibilities | Authority |
|----|-----------|------------------|-----------|
| **AI 1** | `ROLE_ProductManager_Requirements.md` | User focus, problem definition, PRD creation | LEAD - Final say on PRD |
| **AI 2** | `ROLE_BusinessAnalyst_Requirements.md` | Technical specs, validation, feasibility | SUPPORT - Must approve PRD |

### Input Files Required

**Minimum (Session 1):**
- `USER_REQUEST.md` - Your project description

**For Iteration (Session 2+):**
- `USER_REQUEST.md` - Original request
- `USER_RESPONSE.md` - Your answers to clarification questions

### Output Files Produced

**If Requirements Are Clear:**
- `PRD.md` - Product Requirements Document

**If Clarification Needed:**
- `CLARIFICATION_REQUEST.md` - Questions for stakeholder

### Success Signal

Both AIs will signal `[[PROJECT_COMPLETE]]` when:
- PRD.md is created and approved by both, OR
- CLARIFICATION_REQUEST.md is created and ready to send

---

## Detailed Command Examples

### Example 1: First Session (Standard Path)

**Scenario**: You have a clear project idea described in USER_REQUEST.md

**Setup:**
```bash
# Navigate to your project
cd /home/user/projects/my-project

# Create your request file (use your preferred editor)
nano USER_REQUEST.md

# Create artifacts directory
mkdir -p artifacts/prd_session
```

**Command:**
```bash
python /home/dgray/Projects/Orchestrator/run_orchestrated_discussion.py \
  --ai1-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create comprehensive PRD.md documenting all requirements. If critical information is missing, create CLARIFICATION_REQUEST.md instead." \
  --max-turns 15 \
  --log-file artifacts/prd_session/conversation.log
```

**Expected Result:**
- Duration: 10-15 turns
- Output: `PRD.md` (if clear) or `CLARIFICATION_REQUEST.md` (if unclear)
- Log: `artifacts/prd_session/conversation.log`

---

### Example 2: Iteration After Clarification

**Scenario**: First session produced CLARIFICATION_REQUEST.md, you've created USER_RESPONSE.md with answers

**Setup:**
```bash
# Review the clarification request
cat CLARIFICATION_REQUEST.md

# Create your response file
nano USER_RESPONSE.md
```

**Command** (same as before):
```bash
python /home/dgray/Projects/Orchestrator/run_orchestrated_discussion.py \
  --ai1-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and USER_RESPONSE.md, then create comprehensive PRD.md. Request additional clarification only if absolutely necessary." \
  --max-turns 15 \
  --log-file artifacts/prd_session/conversation_round2.log
```

**Expected Result:**
- Duration: 8-12 turns
- Output: `PRD.md` (usually) or another `CLARIFICATION_REQUEST.md` (rarely)
- Log: `artifacts/prd_session/conversation_round2.log`

---

### Example 3: With Project Context

**Scenario**: You have specific standards or constraints to communicate

**Setup:**
```bash
# Create project context file
nano PROJECT_CONTEXT.md
```

**PROJECT_CONTEXT.md example:**
```markdown
# Project Context

## Company Standards
- All financial calculations use Decimal (never float)
- All dates use ISO 8601 format
- All APIs must have OpenAPI spec

## Technical Constraints
- Must run on Python 3.11+
- Must use PostgreSQL for persistence
- Must support Docker deployment

## Compliance Requirements
- GDPR compliant (data privacy)
- SOC 2 compliance needed
- Audit logging required for all user actions
```

**Command:**
```bash
python /home/dgray/Projects/Orchestrator/run_orchestrated_discussion.py \
  --ai1-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and PROJECT_CONTEXT.md, then create comprehensive PRD.md that adheres to our standards and constraints." \
  --max-turns 15 \
  --log-file artifacts/prd_session/conversation.log
```

---

### Example 4: Using Specific AI Models

**Scenario**: You want to use specific AI models for each role

**Recommended Model Assignment:**
- **Product Manager**: Gemini or Claude (good at analysis and requirements)
- **Business Analyst**: Claude or Qwen (good at technical details)

**Command:**
```bash
python /home/dgray/Projects/Orchestrator/run_orchestrated_discussion.py \
  --ai1-model gemini \
  --ai1-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_ProductManager_Requirements.md \
  --ai2-model claude \
  --ai2-instruction-file /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create comprehensive PRD.md." \
  --max-turns 15 \
  --log-file artifacts/prd_session/conversation.log
```

---

## Group System Prompts

The `--group-system-prompt` parameter sets the initial task. Here are recommended prompts for different scenarios:

### Standard PRD Creation
```
"Read USER_REQUEST.md and create comprehensive PRD.md documenting all requirements. If critical information is missing, create CLARIFICATION_REQUEST.md instead."
```

### With Additional Context
```
"Read USER_REQUEST.md and PROJECT_CONTEXT.md, then create comprehensive PRD.md that adheres to our standards and constraints. Request clarification if needed."
```

### After Clarification Round
```
"Read USER_REQUEST.md and USER_RESPONSE.md, then create comprehensive PRD.md. Request additional clarification only if absolutely necessary."
```

### Emphasis on Specific Domain
```
"Read USER_REQUEST.md for a financial application. Create comprehensive PRD.md with special attention to calculation precision, validation rules, and edge cases involving currency."
```

### Quick MVP Focus
```
"Read USER_REQUEST.md and create PRD.md focused on Minimum Viable Product (MVP). Clearly separate must-have features from nice-to-have features."
```

---

## Workflow Patterns

### Pattern A: Single Session Success

```
1. Create USER_REQUEST.md with clear, detailed project description
2. Run session with standard command
3. Review PRD.md output
4. ✅ Done - Move to planning phase
```

**When This Works:**
- Requirements are clear and complete
- No ambiguities in critical decisions
- Examples provided in USER_REQUEST.md
- Edge cases mentioned

**Duration**: 10-15 turns

---

### Pattern B: Clarification Iteration

```
1. Create USER_REQUEST.md (may have some gaps)
2. Run session with standard command
3. Receive CLARIFICATION_REQUEST.md
4. Create USER_RESPONSE.md with answers
5. Run session again (same command, updated prompt)
6. Receive PRD.md
7. ✅ Done - Move to planning phase
```

**When This Works:**
- Initial request has ambiguities
- AIs identify critical missing information
- You can answer the questions
- Second round has sufficient detail

**Duration**: 18-25 turns total (across 2 sessions)

---

### Pattern C: Multiple Clarification Rounds

```
1. Create USER_REQUEST.md
2. Run session → CLARIFICATION_REQUEST.md (Round 1)
3. Create USER_RESPONSE.md
4. Run session → CLARIFICATION_REQUEST.md (Round 2 - rare)
5. Create USER_RESPONSE_2.md
6. Run session → PRD.md
7. ✅ Done - Move to planning phase
```

**When This Happens:**
- Very complex or novel project
- Domain has many unknowns
- Initial request was very high-level

**Duration**: 25-35 turns total (across 3 sessions)

**Note**: If you're getting multiple clarification rounds, consider enriching your USER_REQUEST.md with more detail, examples, and specifics.

---

## Monitoring Session Progress

### Check Logs

```bash
# Follow conversation in real-time
tail -f artifacts/prd_session/conversation.log

# Check completion status
grep "PROJECT_COMPLETE" artifacts/prd_session/conversation.log

# Count turns
grep -c "<<<RESPONSE_START>>>" artifacts/prd_session/conversation.log
```

### Look for Key Indicators

**Session Going Well:**
- Both AIs discussing requirements
- Technical details being specified
- PM and BA collaborating actively
- Questions being answered
- Approaching consensus

**Session May Need Adjustment:**
- Endless debate (same topic for 5+ turns)
- Both AIs seem confused
- Multiple contradictory statements
- No progress toward PRD or clarification

**Action if Stuck:**
- Stop session (Ctrl+C)
- Review conversation log
- Improve USER_REQUEST.md with more detail
- Restart session

---

## Troubleshooting Common Issues

### Issue: AIs Don't Create Any Files

**Symptoms:**
- Session completes but no PRD.md or CLARIFICATION_REQUEST.md
- Log shows AIs discussing but not writing

**Diagnosis:**
- `[PROJECT_DIRECTORY]` variable not replaced
- Permission issues in project directory
- AIs unsure if they have enough information

**Solution:**
```bash
# 1. Check if variable is replaced
grep "\[PROJECT_DIRECTORY\]" /path/to/ROLE_*.md

# 2. Replace manually
sed -i 's|\[PROJECT_DIRECTORY\]|/actual/project/path|g' ROLE_*.md

# 3. Check directory permissions
ls -la /actual/project/path

# 4. Make group-system-prompt more directive
--group-system-prompt "You MUST create either PRD.md or CLARIFICATION_REQUEST.md. Read USER_REQUEST.md and decide which is appropriate."
```

---

### Issue: PRD Is Too Vague

**Symptoms:**
- Requirements say "should be good", "should be fast"
- Validation rules are incomplete
- Edge cases say "TBD"

**Diagnosis:**
- USER_REQUEST.md was too vague
- AIs made assumptions instead of requesting clarification

**Solution:**
1. Review PRD's "Assumptions" section
2. If assumptions are wrong, create feedback document
3. Run another session with clarifications
4. Or improve USER_REQUEST.md and restart

---

### Issue: Too Many Clarification Requests

**Symptoms:**
- Every session requests more clarification
- Questions seem basic or obvious

**Diagnosis:**
- USER_REQUEST.md lacks detail or examples

**Solution:**
Improve USER_REQUEST.md with:
- Concrete examples of use
- Step-by-step workflows
- Expected inputs and outputs (with examples)
- Known edge cases
- Any constraints or requirements

**Example Improvement:**
```markdown
<!-- BEFORE (Vague) -->
I need a calculator for credit cards.

<!-- AFTER (Detailed) -->
I need a calculator that helps me decide if I should transfer my credit card balance.

Current situation:
- I owe $5,000 on a card with 18.5% APR
- I can make $200/month payments
- I found a 0% promotional card (12 months, then 15% APR)

I want to compare:
- Option A: Keep paying current card
- Option B: Transfer to 0% promo card

I need to see:
- How long to pay off each option
- How much interest I'll pay total
- Which option saves me money

Example output:
"Option A: Pay off in 28 months, $600 interest
 Option B: Pay off in 25 months, $250 interest
 Savings with transfer: $350"
```

---

### Issue: Session Times Out

**Symptoms:**
- Hits max-turns limit
- Still no PRD or clarification request

**Diagnosis:**
- AIs debating endlessly
- Unclear on decision criteria
- Waiting for consensus that's not coming

**Solution:**
```bash
# Increase turn limit
--max-turns 20  # or 25

# Make group-system-prompt more specific
--group-system-prompt "You have 15 turns to either: (1) create PRD.md if you have sufficient information, or (2) create CLARIFICATION_REQUEST.md if critical info is missing. Product Manager has final authority on this decision."
```

---

## Best Practices

### 1. Prepare Good USER_REQUEST.md

**Include:**
- Clear problem statement (why this matters)
- Concrete example use case (step-by-step)
- Expected inputs and outputs (with examples)
- Any known edge cases or constraints
- Target users and their context

**Length**: 1-3 pages is typical

### 2. Review Outputs Carefully

**For PRD.md:**
- Read all sections
- Verify assumptions are reasonable
- Check edge cases match your expectations
- Ensure acceptance criteria are testable

**For CLARIFICATION_REQUEST.md:**
- Read all questions
- Provide specific answers (not vague)
- Add examples in your responses
- Answer all questions (mark any you can't answer)

### 3. Use Appropriate Turn Limits

**Recommendations:**
- First session: 15 turns (standard)
- Clarification iteration: 12 turns
- Complex domain: 20 turns
- Simple project: 10 turns

### 4. Save Artifacts

```bash
# Create organized artifact structure
mkdir -p artifacts/prd_session/{round1,round2,round3}

# Save each session separately
--log-file artifacts/prd_session/round1/conversation.log

# Keep all versions of documents
cp PRD.md artifacts/prd_session/round1/PRD_v1.md
```

---

## Example Complete Workflow

```bash
# 1. Setup
cd /home/user/projects/budget-tracker
mkdir -p artifacts/prd_session

# 2. Create USER_REQUEST.md
cat > USER_REQUEST.md << 'EOF'
# User Request - Budget Tracker

## Problem Statement
I lose track of monthly spending and often overspend on non-essentials.

## What I Need
Simple budget tracking:
- Enter monthly income
- Record expenses by category
- See remaining budget
- Warn when approaching limits

## Example Use Case
1. Start of month: Enter income $4,000
2. During month: Log expenses
   - Rent: $1,200
   - Groceries: $400
   - Dining: $150
3. View: Spent $1,750, remaining $2,250
4. Warning if new expense exceeds remaining

## Constraints
- Mobile-friendly
- Simple interface
- No login required (this version)
EOF

# 3. Copy and configure templates
cp /home/dgray/Projects/Orchestrator/templates/prd_universal/ROLE_*.md .

# Replace PROJECT_DIRECTORY variable
PROJECT_DIR=$(pwd)
sed -i "s|\[PROJECT_DIRECTORY\]|$PROJECT_DIR|g" ROLE_*.md

# 4. Run session
python /home/dgray/Projects/Orchestrator/run_orchestrated_discussion.py \
  --ai1-instruction-file ./ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file ./ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create comprehensive PRD.md." \
  --max-turns 15 \
  --log-file artifacts/prd_session/conversation.log

# 5. Review output
cat PRD.md

# 6. If clarification needed, answer and iterate
# (create USER_RESPONSE.md, run again)

# 7. Once PRD approved, move to planning phase
# (use planning templates)
```

---

## Integration with Other Phases

### After PRD is Complete

**Next Step: Planning Phase**
- Input: `PRD.md`
- Roles: Engineering Manager + Technical Lead
- Output: `TASKS.md`, `TECH_DECISIONS.md`

**Next Step: Direct Implementation**
- If project is simple, skip planning
- Give `PRD.md` to developer/team
- Use as specification

### Updating PRD Later

If requirements change during implementation:
1. Create `PRD_UPDATE_REQUEST.md` with changes
2. Run session again with both PRD.md and update request
3. AIs will create `PRD_v2.md`
4. Review changes carefully
5. Update planning/implementation accordingly

---

## Summary Command Reference

**Standard session:**
```bash
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/prd_universal/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file templates/prd_universal/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create PRD.md" \
  --max-turns 15 \
  --log-file artifacts/prd_session/log.txt
```

**Replace [PROJECT_DIRECTORY]:**
```bash
sed -i 's|\[PROJECT_DIRECTORY\]|/your/project/path|g' ROLE_*.md
```

**Monitor progress:**
```bash
tail -f artifacts/prd_session/log.txt
```

**Check completion:**
```bash
grep "PROJECT_COMPLETE" artifacts/prd_session/log.txt
```

---

For more information, see `README.md` in this directory.
