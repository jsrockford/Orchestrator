# Universal PRD Creation Templates

**Version**: 1.0 (Production-Ready)
**Last Updated**: 2025-11-13
**Status**: Ready to Use - NO TODOs

## Overview

This directory contains **production-ready, universal instruction files** for creating Product Requirements Documents (PRDs) through AI collaboration. These files work for **any project type** without modification.

**Key Feature**: Unlike other templates, these have **ZERO TODOs**. They're ready to use immediately for:
- Financial applications
- Games
- Web applications/APIs
- Data processing tools
- CLI/terminal applications
- Mobile apps
- Any other software project

## Why Universal Templates?

The PRD phase is uniquely suited to universality because:

1. **Same goal every time**: Convert stakeholder needs into comprehensive requirements
2. **Same process**: Analyze → Discuss → Document (or request clarification)
3. **Same structure**: All PRDs use the same template sections
4. **Domain knowledge comes from stakeholder**: AIs interview/clarify, not provide domain expertise
5. **Standardized collaboration**: Product Manager (lead) + Business Analyst (technical expert)

**Result**: One set of files works for all projects.

## Files in This Directory

| File | Role | Purpose |
|------|------|---------|
| `ROLE_ProductManager_Requirements.md` | Lead | User-focused requirements, PRD creation, scope definition |
| `ROLE_BusinessAnalyst_Requirements.md` | Support | Technical specifications, validation rules, feasibility |
| `README.md` | Documentation | This file - usage instructions |
| `SESSION_MAPPING.md` | Documentation | Command examples and workflow guidance |

## How to Use

### Step 1: Create USER_REQUEST.md

In your project directory, create a file describing what you want:

```markdown
# User Request - My Project

## Problem Statement
[Describe the problem you're trying to solve]

## What I Need
[Describe what you want the software to do]

## Example Use Case
[Show how someone would use this]

## Inputs
[What information/data will users provide?]

## Expected Outputs
[What should the system produce?]

## Important Considerations
[Any constraints, preferences, or special requirements]
```

**Example USER_REQUEST.md:**
```markdown
# User Request - Budget Tracker

## Problem Statement
I'm losing track of where my money goes each month. I need to see my income vs expenses clearly.

## What I Need
A simple app that lets me:
- Enter my monthly income
- Record expenses by category (rent, food, entertainment, etc.)
- See how much I have left to spend
- Get warnings if I'm overspending

## Example Use Case
1. I open the app at the start of the month
2. I enter my income: $4,000
3. Throughout the month, I record expenses:
   - Rent: $1,200
   - Groceries: $400
   - Dining out: $150
4. The app shows me I've spent $1,750 and have $2,250 remaining
5. If I try to add an expense that exceeds my remaining budget, it warns me

## Inputs
- Monthly income (dollar amount)
- Expenses: amount, category, date
- Budget limits per category (optional)

## Expected Outputs
- Current balance (income - expenses)
- Breakdown by category
- Warnings when approaching/exceeding budget

## Important Considerations
- Should be simple - I'm not tech-savvy
- Mobile-friendly would be nice
- Don't need anything fancy, just functional
```

### Step 2: Run the Orchestrated Discussion

**Replace `[PROJECT_DIRECTORY]`** in both instruction files with your actual project path, then run:

```bash
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/prd_universal/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file templates/prd_universal/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create comprehensive PRD.md. If critical information is missing, create CLARIFICATION_REQUEST.md instead." \
  --max-turns 15 \
  --log-file artifacts/prd_session/conversation.log
```

**Important**: Before running, do a find-and-replace in both .md files:
- Find: `[PROJECT_DIRECTORY]`
- Replace with your actual path: `/home/user/projects/budget-tracker`

Or use this sed command:
```bash
# Set your project directory
PROJECT_DIR="/home/dgray/Projects/MyProject"

# Copy templates to your project
cp templates/prd_universal/*.md my-project/

# Replace the variable
sed -i "s|\[PROJECT_DIRECTORY\]|$PROJECT_DIR|g" my-project/ROLE_*.md
```

### Step 3: Review Output

The AIs will produce one of two outcomes:

**Outcome A: PRD.md Created**
- Comprehensive Product Requirements Document
- Ready for planning phase
- Review and provide feedback if needed

**Outcome B: CLARIFICATION_REQUEST.md Created**
- Questions about ambiguous requirements
- Create USER_RESPONSE.md with answers
- Re-run session with both files available

### Step 4: Iterate if Needed

If clarification was requested:

1. Create `USER_RESPONSE.md` with answers to questions
2. Run session again (same command)
3. AIs will read both USER_REQUEST.md and USER_RESPONSE.md
4. May produce PRD or request more clarification

**Typical iterations**: 1-2 clarification rounds for most projects

## What Makes These Templates Universal?

### Domain-Aware Guidance (Not Domain-Specific)

Instead of having separate templates for financial, gaming, web, etc., these templates include:

**Prompts for Different Domains:**
```markdown
## If Project Appears to Be: Financial
- Ask about calculation methods
- Ask about precision requirements
- Consider rounding rules

## If Project Appears to Be: Game
- Ask about game mechanics
- Ask about win/lose conditions
- Consider difficulty curve

[etc. for all common domains]
```

The AIs **adapt** based on what they see in USER_REQUEST.md.

### Complete Examples for All Domains

The files include real examples for:
- Financial calculations (interest, payments, precision)
- Game development (collision, movement, state)
- Web APIs (endpoints, authentication, validation)
- Data processing (CSV, validation, transformations)
- CLI tools (arguments, output, error handling)

### Smart Clarification Questions

The AIs know what questions to ask for each domain:
- Financial: "Which calculation formula?" "What precision?"
- Games: "What are core mechanics?" "Win/lose conditions?"
- Web: "Authentication method?" "API structure?"
- Data: "How to handle missing values?" "Expected volume?"

## Key Features

### ✅ Production-Ready
- No TODOs to fill in
- Use immediately for any project
- Complete examples and guidance

### ✅ Domain-Adaptive
- Works for financial, gaming, web, data, CLI, etc.
- Provides domain-appropriate guidance
- Asks domain-appropriate clarification questions

### ✅ Iterative Clarification
- AIs request clarification when needed
- Support multiple rounds of Q&A
- No guessing on critical decisions

### ✅ Role Separation
- Product Manager: User focus, problem definition, PRD structure
- Business Analyst: Technical specs, validation rules, feasibility
- Clear collaboration protocols

### ✅ Quality Focus
- Comprehensive PRD template included
- Quality checklists built in
- Both roles must approve before completion

## Expected Session Flow

**Typical Flow (No Clarification Needed):**
```
Turn 1-2:   Both AIs read USER_REQUEST.md independently
Turn 3-4:   AIs discuss what they understood
Turn 5:     Agreement: enough info to proceed
Turn 6-8:   PM drafts PRD, BA provides technical input
Turn 9-10:  BA reviews PRD, provides feedback
Turn 11-12: PM addresses feedback, finalizes PRD
Turn 13-14: Both approve and signal [[PROJECT_COMPLETE]]

Result: PRD.md created
Duration: ~13-14 turns
```

**Flow With Clarification:**
```
SESSION 1:
Turn 1-2:   Both AIs read USER_REQUEST.md
Turn 3-4:   AIs discuss ambiguities
Turn 5:     Agreement: need clarification
Turn 6-7:   Compile questions together
Turn 8:     Create CLARIFICATION_REQUEST.md
Turn 9:     Both signal [[PROJECT_COMPLETE]]

[Human creates USER_RESPONSE.md]

SESSION 2:
Turn 1-2:   Both AIs read USER_REQUEST.md + USER_RESPONSE.md
Turn 3:     Agreement: now have enough info
Turn 4-8:   Create PRD as above
Turn 9-10:  Both approve and signal [[PROJECT_COMPLETE]]

Result: PRD.md created
Duration: ~18 turns total (across 2 sessions)
```

## Customization (Optional)

While these templates work universally, you CAN customize if desired:

### Adding Project-Specific Context

If you have specific standards or requirements, add a `PROJECT_CONTEXT.md` file in your project directory and reference it in the group-system-prompt:

```bash
--group-system-prompt "Read USER_REQUEST.md and PROJECT_CONTEXT.md, then create comprehensive PRD.md."
```

**PROJECT_CONTEXT.md example:**
```markdown
# Project Context

## Our Standards
- All calculations must use Decimal (company policy)
- All currency must be USD
- Precision: 2 decimal places
- Follow our PRD template exactly

## Technical Constraints
- Must work on Python 3.11+
- Must use PostgreSQL database
- Must be Docker-deployable

## Compliance
- HIPAA compliance required
- Data must be encrypted at rest
- Audit logging required
```

### Adjusting Project Directory Variable

The `[PROJECT_DIRECTORY]` variable appears in the security boundary section. Replace it with your actual project path before using.

**Quick replace command:**
```bash
sed -i 's|\[PROJECT_DIRECTORY\]|/actual/path/to/project|g' ROLE_*.md
```

Or manually edit both files.

## Success Criteria

You'll know the session was successful when:

- ✅ PRD.md exists and is comprehensive
- ✅ All sections of the PRD template are filled in
- ✅ Requirements are specific and testable
- ✅ Edge cases are identified
- ✅ Technical specifications are clear
- ✅ Both AIs signaled [[PROJECT_COMPLETE]]

**PRD Quality Indicators:**
- Problem statement clearly explains WHY
- All inputs have data types and constraints
- All outputs have format specifications
- Validation rules are complete
- Acceptance criteria are measurable
- Assumptions are documented with rationale
- No "TBD" items remain

## Troubleshooting

### Issue: AIs Produce Vague Requirements

**Symptom**: Requirements say "should be fast", "should be accurate", etc.

**Solution**: In USER_REQUEST.md, provide concrete examples:
- ❌ "Should be fast"
- ✅ "Should show results in less than 2 seconds"

### Issue: Too Many Clarification Requests

**Symptom**: AIs keep requesting clarification session after session

**Cause**: USER_REQUEST.md is too vague or missing critical information

**Solution**: Provide more detail upfront:
- Include concrete examples of use
- Specify expected inputs and outputs
- Describe edge cases you're aware of
- Show example results or screenshots

### Issue: PRD Misses Key Requirements

**Symptom**: PRD is created but missing things you wanted

**Solution**: Be explicit in USER_REQUEST.md:
- List all must-have features
- Provide complete use case walkthrough
- Mention all constraints upfront

### Issue: AIs Don't Request Clarification When They Should

**Symptom**: PRD created with assumptions that are wrong

**Solution**: This is rare with these templates, but if it happens:
- Review the PRD's "Assumptions" section
- Check if assumptions are documented
- Provide feedback and iterate

### Issue: Path Issues (Forbidden Paths Error)

**Symptom**: AIs refuse to create files, citing forbidden paths

**Solution**: Ensure `[PROJECT_DIRECTORY]` variable is replaced with valid path:
```bash
# Check if variable is still present
grep "\[PROJECT_DIRECTORY\]" ROLE_*.md

# Replace it
sed -i 's|\[PROJECT_DIRECTORY\]|/home/user/my-project|g' ROLE_*.md
```

## Tips for Best Results

### 1. Write Clear USER_REQUEST.md

**Good Elements:**
- Clear problem statement (why this matters)
- Concrete example use case (step-by-step)
- Specific inputs and outputs
- Known edge cases or concerns
- Any constraints or requirements

**Poor Elements:**
- Vague descriptions ("make it good")
- No examples
- Missing critical context
- Assumptions about what AIs "should know"

### 2. Be Prepared to Iterate

- First session might request clarification - that's good!
- AIs asking questions = they're being thorough
- Answer clarification questions specifically
- Usually 1-2 rounds gets you a solid PRD

### 3. Review PRD Before Next Phase

- Read the PRD thoroughly
- Verify it matches your intent
- Check assumptions section
- Ensure nothing critical is missing
- Provide feedback if needed (can run another session)

### 4. Use PRD as Contract

- PRD becomes the "source of truth"
- Planning phase will reference it
- Implementation phase will build from it
- Changes to requirements require PRD updates

## Next Steps After PRD

Once you have an approved PRD.md:

1. **Move to Planning Phase**
   - Use planning instruction templates (if available)
   - Input: PRD.md
   - Output: TASKS.md, TECH_DECISIONS.md

2. **Move to Implementation Phase**
   - Use implementation instruction templates
   - Input: PRD.md, TASKS.md, TECH_DECISIONS.md
   - Output: Working code

3. **Or Use PRD Directly**
   - Give PRD.md to your development team
   - Use it as specification for implementation
   - Reference during testing and validation

## Examples

See `docs/instruction_file_examples.md` for complete examples of PRDs created using these templates for:
- Financial calculator
- Snake game
- Web API service
- Data processing tool
- Web UI enhancement

## Support

If you encounter issues:

1. Check this README troubleshooting section
2. Review `docs/instruction_file_creation_guide.md`
3. See example PRDs in documentation
4. Check that [PROJECT_DIRECTORY] variable is replaced
5. Verify USER_REQUEST.md has sufficient detail

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-13 | Initial production-ready universal templates |

---

**Remember**: These templates are designed to work for ANY project type. You don't need different templates for financial vs gaming vs web - the same files adapt to your project based on what you describe in USER_REQUEST.md.

The key is providing a clear, detailed USER_REQUEST.md. The AIs will handle the rest!
