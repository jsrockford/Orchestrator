# Instruction File Generator Guide

**Version**: 1.2
**Last Updated**: 2025-11-16
**Purpose**: Documentation for the interactive instruction file generation script

## Changelog

**v1.2** (2025-11-16):
- ✅ Implemented Phase 3 refinement using ARCHITECTURE.md, PROJECT_TASKS.md, and RISKS.md
- ✅ Added RISKS.md parsing to extract critical/high risks and mitigation strategies
- ✅ Added ARCHITECTURE.md parsing to extract tech stack, components, design patterns, directory structure
- ✅ Enhanced PROJECT_TASKS.md parsing to support ### section format with **ID:** blocks
- ✅ Added prominent response delimiter reminders to prevent missing_output errors
- ✅ Auto-fills Technology Guidance section with extracted tech stack and components
- ✅ Auto-fills Common Pitfalls section with risks and mitigations from RISKS.md
- ✅ Auto-fills Workflow Phases with milestone names and specific TASK-IDs

**v1.1** (2025-11-13):
- ✅ Implemented Phase 2 refinement using PRD.md
- ✅ Added staged refinement workflow
- ✅ Command-line argument parsing for refine mode

**v1.0** (Initial):
- ✅ Interactive project interview
- ✅ Automatic instruction file generation
- ✅ Support for 2-phase and 3-phase workflows
- ✅ Role selection and template customization

## Overview

The Instruction File Generator (`scripts/generate_instruction_files.py`) is an interactive Python script that creates customized instruction files for your Orchestrator projects. Instead of manually copying and editing templates, the script interviews you about your project and generates appropriate files automatically.

## Quick Start

### Stage 1: Initial Generation

```bash
# From the repository root
python scripts/generate_instruction_files.py
```

The script will:
1. Ask questions about your project
2. Recommend appropriate workflow phases
3. Help you select roles for each phase
4. Generate customized instruction files
5. Create supporting documentation

### Stage 2: Phase 2 Refinement (After PRD Exists)

```bash
# After completing Phase 1 and creating PRD.md
python scripts/generate_instruction_files.py --refine --phase 2 --prd-file ./PRD.md
```

This will:
1. Parse PRD.md to extract requirements and success criteria
2. Auto-fill Category 5 TODOs (examples, artifacts, workflow structure) in Phase 2 templates
3. Preserve all human customizations (Categories 1-4: domain, tech, authority, workflow)

### Stage 3: Phase 3 Refinement (After ARCHITECTURE Exists)

```bash
# After completing Phase 2 and creating ARCHITECTURE.md, PROJECT_TASKS.md, and RISKS.md
python scripts/generate_instruction_files.py --refine --phase 3 \
  --architecture-file ./ARCHITECTURE.md \
  --tasks-file ./PROJECT_TASKS.md \
  --risks-file ./RISKS.md
```

This will:
1. Parse ARCHITECTURE.md to extract tech stack, components, design patterns, directory structure
2. Parse PROJECT_TASKS.md to extract tasks, milestones, effort estimates
3. Parse RISKS.md to extract critical/high risks and mitigation strategies
4. Auto-fill Category 5 TODOs in Phase 3 templates (examples, artifacts, workflow structure)
5. Preserve all human customizations (Categories 1-4: domain, tech, authority, workflow)

## What Gets Generated

For each project, the generator creates:

**Instruction Files** (one per role per phase):
- `ROLE_[RoleName]_[PhaseName].md` - Customized for your project

**Supporting Documentation**:
- `README.md` - Workflow overview
- `SESSION_MAPPING.md` - Usage instructions for each session
- `USER_REQUEST.md` - Template for stakeholder input
- `project_config.json` - Configuration reference

**Output Location**:
```
templates/projects/[YourProjectName]/
├── ROLE_ProductManager_Requirements.md
├── ROLE_BusinessAnalyst_Requirements.md
├── ROLE_EngineeringManager_Planning.md
├── ROLE_TechnicalLead_Planning.md
├── ROLE_LeadDeveloper_Implementation.md
├── ROLE_CodeReviewer_Implementation.md
├── README.md
├── SESSION_MAPPING.md
├── USER_REQUEST.md
└── project_config.json
```

## Interview Process

### Step 1: Project Basics

The generator asks about core project information:

**Project Name**
- What to call your project
- Example: "Credit Card Calculator"

**Project Path**
- Absolute path where development happens
- Example: `/home/user/Projects/CreditCardCalc`

**Project Type**
Choose from:
1. CLI/Terminal Application
2. Web Application (full-stack)
3. Web UI for Existing Application
4. Game
5. Library/Package
6. API/Service
7. Data Processing/Analysis
8. Other

**Domain/Industry**
Choose from:
1. Financial/Accounting
2. Gaming
3. Healthcare
4. E-commerce
5. Education
6. General/Other

**Technology Stack**
Choose from:
1. Python
2. JavaScript/Node.js
3. Python + React
4. Python + Vue
5. Other

**Project Description**
- Brief 1-2 sentence description
- Used in generated documentation

**Existing Code**
- Are you enhancing existing code?
- If yes, path to existing code

### Step 2: Workflow Phases

Based on your project type and complexity, the generator recommends a workflow:

**2-Phase Workflow** (simplified)
- Recommended for: Simple CLI tools, enhancement projects
- Phase 1: Planning
- Phase 2: Implementation
- Skips PRD creation

**3-Phase Workflow** (standard)
- Recommended for: Most projects
- Phase 1: Requirements (PRD)
- Phase 2: Planning
- Phase 3: Implementation
- Full lifecycle coverage

**Decision Factors**:
- Simple CLI tool + no existing code → Offer 2-phase option
- Enhancement to existing code → Offer 2-phase option
- Everything else → Use 3-phase workflow

### Step 3: Role Selection

For each phase, select 2-4 AI roles from recommended options.

**Phase 1: Requirements** (if using 3-phase)
- Product Manager (lead) ⭐ Recommended
- Business Analyst ⭐ Recommended
- UX Designer
- Security Analyst
- Domain Expert (appears if domain-specific)

**Phase 2: Planning**
- Engineering Manager (lead) ⭐ Recommended
- Technical Lead ⭐ Recommended
- Full Stack Architect
- Security Architect

**Phase 3: Implementation**
- Lead Developer (lead) ⭐ Recommended
- Code Reviewer ⭐ Highly Recommended
- QA Engineer
- Security Reviewer
- Performance Engineer

**Selection Tips**:
- Always include recommended (⭐) roles
- 2 roles per phase is the sweet spot
- First role selected becomes the lead
- More roles = more collaboration but slower

### Step 4: Confirmation

The generator shows a summary of your choices:

```
CONFIGURATION SUMMARY
======================================================================
Project Name: Budget Tracker
Project Path: /home/user/Projects/BudgetTracker
Project Type: webapp
Domain: financial
Tech Stack: python-react
Description: A web application for tracking personal budgets
Number of Phases: 3

Phase 1 (Requirements):
  - ProductManager
  - BusinessAnalyst

Phase 2 (Planning):
  - EngineeringManager
  - TechnicalLead

Phase 3 (Implementation):
  - LeadDeveloper
  - CodeReviewer

This will generate 6 instruction files plus documentation.

Proceed with generation? [Y/n]:
```

Review carefully - this determines what files get created.

### Step 5: Generation

The script creates all files with:
- Security boundaries prepended
- Response delimiter protocol
- Project-specific variables replaced
- Role-specific templates

Progress output:
```
Generating instruction files...
  Created: ROLE_ProductManager_Requirements.md
  Created: ROLE_BusinessAnalyst_Requirements.md
  Created: ROLE_EngineeringManager_Planning.md
  Created: ROLE_TechnicalLead_Planning.md
  Created: ROLE_LeadDeveloper_Implementation.md
  Created: ROLE_CodeReviewer_Implementation.md
  Created: README.md
  Created: SESSION_MAPPING.md
  Created: USER_REQUEST.md (template)
  Created: project_config.json
```

## Post-Generation Steps

### Required Customization

Generated files contain `TODO:` markers where you must add project-specific content:

**Search for TODOs**:
```bash
cd templates/projects/YourProjectName
grep -r "TODO:" *.md
```

**What to Customize**:

1. **Domain-Specific Guidance**
   - Add formulas, calculations, patterns specific to your domain
   - Example: Financial apps need Decimal precision guidance
   - Example: Games need frame-rate independence patterns

2. **Technology-Specific Examples**
   - Code examples in your tech stack
   - Best practices for your framework
   - Common pitfalls in your language

3. **Detailed Workflow Phases**
   - Break down each phase into specific steps
   - Add exit criteria for each mini-phase
   - Define progression checkpoints

4. **Common Pitfalls**
   - Anti-patterns specific to your project type
   - Mistakes you've seen before
   - Edge cases often missed

5. **Completion Criteria**
   - Specific "Definition of Done" for your project
   - Measurable success criteria
   - Quality standards

### Example Customization

**Before (generated):**
```markdown
## Financial Domain Guidance

<!-- TODO: Add domain-specific guidance for financial projects -->
```

**After (customized):**
```markdown
## Financial Domain Guidance

### Decimal Precision (CRITICAL)

**Always use Decimal for currency:**
```python
from decimal import Decimal

# ✅ CORRECT
principal = Decimal("10000.00")
interest_rate = Decimal("0.185")
interest = principal * interest_rate

# ❌ WRONG
principal = 10000.00  # Float causes rounding errors
```

### Interest Calculation Formulas

**Simple Interest:**
```
I = P × r × t
```

Where:
- P = Principal (Decimal)
- r = Annual rate (Decimal, e.g., 0.185 for 18.5%)
- t = Time in years (Decimal)
```

## Staged Refinement Workflow (NEW)

The generator now supports a **3-stage workflow** that reduces manual TODO completion by auto-filling examples and patterns as artifacts become available.

### Why Staged Refinement?

**Problem:** When you first generate instruction files, many sections contain TODOs because critical information doesn't exist yet:
- Phase 2 templates can't reference specific requirements (PRD doesn't exist)
- Phase 3 templates can't show architecture-specific code examples (ARCHITECTURE doesn't exist)

**Solution:** Run the generator again after each phase completes, using artifacts as input.

### The Complete Workflow

#### Stage 1: Initial Generation (Before Phase 1)

```bash
python scripts/generate_instruction_files.py
```

**What happens:**
- Interactive interview about your project
- Generates skeleton instruction files for all phases
- Creates supporting docs (README, SESSION_MAPPING, USER_REQUEST template)
- All files contain TODOs for content that requires context

**What you do:**
- Fill **Category 1-4 TODOs** (see TODO Taxonomy below)
- Create USER_REQUEST.md with your project requirements
- Run Phase 1 orchestration session

**Phase 1 output:** PRD.md

---

#### Stage 2: Phase 2 Refinement (After PRD Exists)

```bash
cd /path/to/your/project
python scripts/generate_instruction_files.py --refine --phase 2 --prd-file ./PRD.md
```

**What happens:**
- Reads PRD.md and extracts:
  - Functional requirements (FR-1, FR-2, etc.)
  - Non-functional requirements (NFR-1, NFR-2, etc.)
  - Data models (class/entity names)
  - Success criteria
- Updates Phase 2 instruction files by filling:
  - `[TODO: List required input files]` → "- PRD.md"
  - `[TODO: List expected output files]` → "- ARCHITECTURE.md\n- PROJECT_TASKS.md"
  - `[TODO: Define completion criteria]` → Success criteria from PRD
  - `[TODO: Activity Name]` → "PRD Analysis and Component Identification"
- **Preserves your customizations** - only replaces exact TODO markers

**Output example:**
```
Reading PRD from: ./PRD.md
  Extracted 5 functional requirements
  Extracted 3 non-functional requirements
  Found 4 data model references

Project directory: /home/user/Projects/MyProject

Found 2 Phase 2 instruction files to refine:
  - ROLE_EngineeringManager_Planning.md
  - ROLE_TechnicalLead_Planning.md

Refining: ROLE_EngineeringManager_Planning.md...
  ✓ Filled Input Artifacts
  ✓ Filled Output Artifacts
  ✓ Filled Success Criteria
  ✓ Filled Workflow Phase structure
  💾 Saved changes

Refining: ROLE_TechnicalLead_Planning.md...
  ✓ Filled Input Artifacts
  ✓ Filled Output Artifacts
  ✓ Filled Success Criteria
  💾 Saved changes

Phase 2 Refinement Complete!
  2 file(s) updated

Next steps:
  1. Review the updated files for accuracy
  2. Fill remaining Domain/Tech TODOs
  3. Run Phase 2 orchestration session
```

**What you do:**
- Review auto-filled content for accuracy
- Fill any remaining domain/tech-specific TODOs
- Run Phase 2 orchestration session

**Phase 2 output:** ARCHITECTURE.md, PROJECT_TASKS.md, RISKS.md

---

#### Stage 3: Phase 3 Refinement (After ARCHITECTURE Exists)

```bash
cd /path/to/your/project
python scripts/generate_instruction_files.py --refine --phase 3 \
  --architecture-file ./ARCHITECTURE.md \
  --tasks-file ./PROJECT_TASKS.md \
  --risks-file ./RISKS.md
```

**What happens:**
- Reads ARCHITECTURE.md and extracts:
  - Technology stack (Python version, libraries, frameworks)
  - Components and modules to implement
  - Design patterns to follow
  - Directory structure
- Reads PROJECT_TASKS.md and extracts:
  - All tasks with IDs (TASK-001, TASK-002, etc.)
  - Milestones and phases
  - Effort estimates
  - High-priority tasks
- Reads RISKS.md and extracts:
  - Critical and High severity risks
  - Mitigation strategies
  - Risk-to-task mappings
- Updates Phase 3 instruction files by filling:
  - `[TODO: List required input files]` → "PRD.md\n- ARCHITECTURE.md\n- PROJECT_TASKS.md\n- RISKS.md"
  - `[TODO: List expected output files]` → Source code, tests, README, requirements
  - `[TODO: Define completion criteria]` → All requirements implemented, all tasks complete, tests passing
  - `<!-- TODO: Add technology-specific patterns -->` → Tech stack, components, design patterns, directory structure
  - `<!-- TODO: Add project-specific pitfalls -->` → Critical/High risks with mitigation strategies
  - `[TODO: Activity Name]` → Task-driven workflow with milestone names and specific TASK-IDs
- **Preserves your customizations** - only replaces exact TODO markers

**Output example:**
```
Reading ARCHITECTURE.md from: ./scratch/ARCHITECTURE.md
Reading PROJECT_TASKS.md from: ./scratch/PROJECT_TASKS.md
Reading RISKS.md from: ./scratch/RISKS.md
  Extracted 8 technology stack items
  Extracted 5 components
  Extracted 35 tasks (256 hours)
  Extracted 3 milestones
  Extracted 2 critical risks, 4 high risks

Project directory: /home/user/Projects/MyProject

Found 2 Phase 3 instruction files to refine:
  - ROLE_LeadDeveloper_Implementation.md
  - ROLE_CodeReviewer_Implementation.md

Refining: ROLE_LeadDeveloper_Implementation.md...
  ✓ Filled Input Artifacts
  ✓ Filled Output Artifacts
  ✓ Filled Success Criteria
  ✓ Filled Technology Guidance
  ✓ Filled Common Pitfalls from RISKS.md
  ✓ Filled Workflow Phase structure with tasks
  💾 Saved changes

Refining: ROLE_CodeReviewer_Implementation.md...
  ✓ Filled Input Artifacts
  ✓ Filled Output Artifacts
  ✓ Filled Success Criteria
  ✓ Filled Technology Guidance
  ✓ Filled Common Pitfalls from RISKS.md
  💾 Saved changes

Phase 3 Refinement Complete!
  2 file(s) updated

Next steps:
  1. Review the updated files for accuracy
  2. Fill remaining Domain/Tech TODOs if any
  3. Run Phase 3 orchestration session

IMPORTANT: Ensure all AI models use response delimiters:
  <<<RESPONSE_START>>>
  [your response here]
  <<<RESPONSE_END>>>
```

**What you do:**
- Review auto-filled content for accuracy
- Fill any remaining domain/tech-specific TODOs
- Run Phase 3 orchestration session

**Phase 3 output:** Source code, tests, documentation, completed project

---

### TODO Taxonomy (What Gets Auto-Filled vs. Manual)

Staged refinement follows a clear taxonomy of which TODOs can be automated:

| Category | Owner | When Filled | Auto-Fillable? |
|----------|-------|-------------|----------------|
| **Cat 1: Domain** | Domain expert | Stage 1 | ❌ No - Requires expertise (regulations, compliance, domain patterns) |
| **Cat 2: Tech Stack** | Lead dev/architect | Stage 1 | ❌ No - Requires expertise (framework patterns, best practices) |
| **Cat 3: Authority** | PM/team lead | Stage 1 | ❌ No - Requires team knowledge (decision-making rules, governance) |
| **Cat 4: Workflow** | PM | Stage 1 | ❌ No - Requires project planning (phase structure, checkpoints) |
| **Cat 5: Examples** | Auto or manual | Stage 2/3 | ✅ Yes - Can extract from PRD/ARCHITECTURE (file names, success criteria, basic structure) |

**Key principle:** Staged refinement fills **Category 5 TODOs** (examples, artifacts, patterns) while leaving **Categories 1-4** (domain, tech, authority, workflow) for human experts.

### Command Reference

**Help:**
```bash
python scripts/generate_instruction_files.py --help
```

**Stage 1 (Initial):**
```bash
python scripts/generate_instruction_files.py
```

**Stage 2 (Refine Phase 2):**
```bash
python scripts/generate_instruction_files.py \
  --refine \
  --phase 2 \
  --prd-file ./PRD.md \
  [--project-dir ./path/to/project]  # Optional: defaults to PRD parent directory
```

**Stage 3 (Refine Phase 3):**
```bash
python scripts/generate_instruction_files.py \
  --refine \
  --phase 3 \
  --architecture-file ./ARCHITECTURE.md \
  --tasks-file ./PROJECT_TASKS.md \
  --risks-file ./RISKS.md \
  [--project-dir ./path/to/project]  # Optional: defaults to ARCHITECTURE parent directory
```

### What Refinement Preserves

**Safe operations:**
- ✅ Only replaces exact TODO marker strings (e.g., `[TODO: List required input files]`)
- ✅ Leaves all custom text untouched
- ✅ Preserves formatting and structure
- ✅ Never modifies sections without TODO markers

**Example:**

**Before refinement (you added custom content):**
```markdown
**Input Artifacts:**
- PRD.md (already added by you manually)
- Reference documents from stakeholder

**Output Artifacts:**
- [TODO: List expected output files]
```

**After refinement:**
```markdown
**Input Artifacts:**
- PRD.md (already added by you manually)
- Reference documents from stakeholder

**Output Artifacts:**
- ARCHITECTURE.md
- PROJECT_TASKS.md
- RISKS.md
```

Notice: Your custom "Reference documents" line is preserved, TODO is replaced.

### Benefits of Staged Refinement

1. **Reduces manual work:** Category 5 TODOs auto-filled from artifacts (30-40% of TODOs)
2. **Context-aware templates:** Phase 2/3 templates reference actual project files (PRD.md, ARCHITECTURE.md)
3. **Maintains quality:** Categories 1-4 still require human expertise where it matters
4. **Safe updates:** Preserves your customizations, only fills TODOs
5. **Iterative improvement:** Can re-run refinement as artifacts evolve

### Limitations

**What refinement CANNOT do:**
- ❌ Add domain-specific guidance (financial regulations, healthcare compliance)
- ❌ Add technology-specific patterns (React hooks, Python async best practices)
- ❌ Predict common pitfalls (requires experience)
- ❌ Make authority decisions (who has final say on architecture)
- ❌ Extract complex logic from natural language requirements

**Why:** These require deep contextual knowledge beyond what can be reliably parsed from text.

For details on why automation has limits, see `templates/challenges.md`.

## Using Generated Files

### 1. Complete Customization

Before using the files:
- Replace all `TODO:` markers
- Add domain and technology guidance
- Test with simple examples
- Iterate based on results

### 2. Create Input Files

**For Phase 1** (Requirements):
Edit `USER_REQUEST.md` with your actual project requirements:
```markdown
# User Request - Budget Tracker

## Problem Statement
I want to track my monthly income and expenses to see where my money goes.

## What I Need
A web application that lets me:
- Enter income sources and amounts
- Categorize expenses
- See monthly summaries
- Identify spending patterns

[... continue with details ...]
```

**For Phase 2** (Planning):
Use `PRD.md` output from Phase 1

**For Phase 3** (Implementation):
Use `PRD.md` and `TASKS.md` from previous phases

### 3. Run Sessions

See generated `SESSION_MAPPING.md` for exact commands:

```bash
# Phase 1: Requirements
python run_orchestrated_discussion.py \
  --ai1-instruction-file templates/projects/BudgetTracker/ROLE_ProductManager_Requirements.md \
  --ai2-instruction-file templates/projects/BudgetTracker/ROLE_BusinessAnalyst_Requirements.md \
  --group-system-prompt "Read USER_REQUEST.md and create comprehensive PRD" \
  --max-turns 10 \
  --log-file artifacts/phase1/conversation.log
```

### 4. Iterate and Improve

After running sessions:
- Note what worked well
- Identify confusing sections
- Add missing guidance
- Update instruction files
- Version your changes

## Advanced Usage

### Regenerating for Different Project Types

Use the same script multiple times to create instruction files for different project types:

```bash
# First project: CLI tool
python scripts/generate_instruction_files.py
# ... answer questions for CLI project ...

# Second project: Web app
python scripts/generate_instruction_files.py
# ... answer questions for web app ...
```

Each creates a separate directory under `templates/projects/`.

### Customizing Role Templates

The generator uses built-in role templates. For advanced customization:

1. Generate initial files with the script
2. Manually edit generated files to add project-specific content
3. Save customized version as a new template
4. Reuse for similar projects

### Modifying the Generator

The generator script is in `scripts/generate_instruction_files.py`. You can modify it to:

- Add new project types
- Add new domains
- Add new tech stacks
- Customize role templates
- Change interview flow
- Add validation logic

**Key Classes**:
- `ProjectConfig` - Configuration data structure
- `InstructionFileGenerator` - Main generator logic

**Key Methods**:
- `_interview_user()` - Question flow
- `_select_roles()` - Role selection logic
- `_generate_role_file()` - File generation
- `_get_role_template()` - Role content template

## Troubleshooting

### Issue: Script Fails to Run

**Error**: `python: command not found` or `python3: command not found`

**Solution**:
```bash
# Try python3 explicitly
python3 scripts/generate_instruction_files.py

# Or check your Python installation
which python
which python3
```

### Issue: Permission Denied

**Error**: `Permission denied: templates/projects/MyProject`

**Solution**:
```bash
# Check directory permissions
ls -la templates/

# Create projects directory if missing
mkdir -p templates/projects
```

### Issue: Generated Files Missing Content

**Symptom**: Files are created but have many TODO markers

**Explanation**: This is expected! The generator creates skeleton files that you must customize.

**Solution**: Review "Post-Generation Steps" section above and customize each file.

### Issue: Wrong Roles Selected

**Symptom**: Realized you need different roles after generation

**Solution**:
1. Delete the generated project directory
2. Run the generator again
3. Select different roles

Or manually edit `SESSION_MAPPING.md` to use different role combinations.

### Issue: Need Different Workflow

**Symptom**: 2-phase vs 3-phase wasn't right for your project

**Solution**:
1. Delete generated directory
2. Run generator again
3. Make different choice at workflow phase selection

## Examples

### Example 1: Simple CLI Calculator

**Inputs**:
- Project Name: "Tip Calculator"
- Project Type: CLI/Terminal Application
- Domain: General
- Tech Stack: Python
- Workflow: 2-phase (simplified)
- Phase 1 Roles: EngineeringManager, TechnicalLead
- Phase 2 Roles: LeadDeveloper, CodeReviewer

**Output**:
```
templates/projects/Tip_Calculator/
├── ROLE_EngineeringManager_Planning.md
├── ROLE_TechnicalLead_Planning.md
├── ROLE_LeadDeveloper_Implementation.md
├── ROLE_CodeReviewer_Implementation.md
├── README.md
├── SESSION_MAPPING.md
├── USER_REQUEST.md
└── project_config.json
```

### Example 2: Financial Web App

**Inputs**:
- Project Name: "Investment Portfolio Tracker"
- Project Type: Web Application
- Domain: Financial/Accounting
- Tech Stack: Python + React
- Workflow: 3-phase (standard)
- Phase 1 Roles: ProductManager, BusinessAnalyst, FinancialExpert
- Phase 2 Roles: EngineeringManager, TechnicalLead
- Phase 3 Roles: LeadDeveloper, CodeReviewer, QAEngineer

**Output**:
```
templates/projects/Investment_Portfolio_Tracker/
├── ROLE_ProductManager_Requirements.md
├── ROLE_BusinessAnalyst_Requirements.md
├── ROLE_FinancialExpert_Requirements.md
├── ROLE_EngineeringManager_Planning.md
├── ROLE_TechnicalLead_Planning.md
├── ROLE_LeadDeveloper_Implementation.md
├── ROLE_CodeReviewer_Implementation.md
├── ROLE_QAEngineer_Implementation.md
├── README.md
├── SESSION_MAPPING.md
├── USER_REQUEST.md
└── project_config.json
```

### Example 3: Game Development

**Inputs**:
- Project Name: "Snake Game"
- Project Type: Game
- Domain: Gaming
- Tech Stack: Python
- Workflow: 3-phase
- Phase 1 Roles: ProductManager (acting as Game Designer), GamingExpert
- Phase 2 Roles: EngineeringManager, TechnicalLead
- Phase 3 Roles: LeadDeveloper, CodeReviewer

**Output**: Similar structure with game-specific roles

## Best Practices

### 1. Start Simple

For your first project:
- Choose a simple project type
- Use standard 3-phase workflow
- Select only recommended (⭐) roles
- Focus on customization quality over quantity

### 2. Iterate on Templates

After using generated files:
- Note what sections were most useful
- Identify gaps in guidance
- Update and improve
- Build a library of refined templates

### 3. Reuse Configurations

For similar projects:
- Save `project_config.json` from successful projects
- Use as reference for similar projects
- Copy domain guidance sections
- Build expertise in your domain

### 4. Version Control

Track instruction files in git:
```bash
git add templates/projects/YourProject/
git commit -m "Add instruction files for YourProject"
```

Benefits:
- Track improvements over time
- Revert if changes don't work
- Share with team
- Document evolution

### 5. Test Before Production

Before using instruction files on real projects:
1. Generate files
2. Customize thoroughly
3. Test with simple example scenario
4. Review AI outputs
5. Refine based on results
6. Then use for real work

## Integration with Orchestrator

### Running Generated Sessions

The generator creates `SESSION_MAPPING.md` with exact commands, but here's the general pattern:

```bash
# Phase 1: Requirements
python run_orchestrated_discussion.py \
  --ai1-instruction-file [path to ROLE_1_Requirements.md] \
  --ai2-instruction-file [path to ROLE_2_Requirements.md] \
  --group-system-prompt "[Phase-specific prompt]" \
  --max-turns 10

# Phase 2: Planning
python run_orchestrated_discussion.py \
  --ai1-instruction-file [path to ROLE_1_Planning.md] \
  --ai2-instruction-file [path to ROLE_2_Planning.md] \
  --group-system-prompt "[Phase-specific prompt]" \
  --max-turns 10

# Phase 3: Implementation
python run_orchestrated_discussion.py \
  --ai1-instruction-file [path to ROLE_1_Implementation.md] \
  --ai2-instruction-file [path to ROLE_2_Implementation.md] \
  --group-system-prompt "[Phase-specific prompt]" \
  --max-turns 20
```

### Artifacts Flow

```
Phase 1 Output: PRD.md
        ↓
Phase 2 Input: PRD.md
Phase 2 Output: TASKS.md, TECH_DECISIONS.md
        ↓
Phase 3 Input: PRD.md, TASKS.md, TECH_DECISIONS.md
Phase 3 Output: Code files, tests, documentation
```

## Implemented Features

✅ **Staged Refinement** (v1.2):
- **Phase 2 refinement** using PRD.md (auto-fills Category 5 TODOs)
- **Phase 3 refinement** using ARCHITECTURE.md, PROJECT_TASKS.md, and RISKS.md (auto-fills Category 5 TODOs)
- Command-line argument parsing for refine mode
- Safe TODO replacement that preserves customizations
- PRD parsing to extract requirements, data models, success criteria
- ARCHITECTURE parsing to extract tech stack, components, design patterns, directory structure
- PROJECT_TASKS parsing to extract tasks, milestones, effort estimates (supports ### section format with **ID:** blocks)
- RISKS parsing to extract critical/high risks and mitigation strategies
- Prominent delimiter reminders to prevent missing_output errors

## Future Enhancements

Planned improvements to the generator:

1. **Enhanced Parsing**: Support more PRD/ARCHITECTURE formats and edge cases
2. **More Role Templates**: Pre-built templates for all common roles
3. **Domain Libraries**: Pre-written domain guidance for financial, gaming, etc.
4. **Tech Stack Libraries**: Pre-written examples for Python, React, etc.
5. **Project Import**: Import existing project config and regenerate
6. **Template Marketplace**: Share and discover community templates
7. **AI-Assisted Customization**: Use AI to help complete TODO sections
8. **Backup/Diff Mode**: Show what will change before applying refinements

## Related Documentation

- `instruction_file_creation_guide.md` - Methodology and concepts
- `instruction_file_templates.md` - Template reference with variables
- `role_authority_patterns.md` - Decision-making patterns
- `templates/ALL_MODELS_TEMPLATE.md` - Base template for all files

## Support

If you encounter issues:

1. Check this documentation
2. Review generated `README.md` in your project directory
3. Check `project_config.json` for configuration details
4. See main Orchestrator documentation
5. File an issue with details of your use case

---

**Script Location**: `scripts/generate_instruction_files.py`
**Generated Files Location**: `templates/projects/[YourProjectName]/`
**Version**: 1.2
**Author**: Orchestrator Development Team
