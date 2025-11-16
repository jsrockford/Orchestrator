# Challenges in Automating Instruction File Generation

## Purpose of This Document

This document explains why automating the creation of Phase 2 (Planning) and Phase 3 (Implementation) instruction files is significantly more difficult than it might appear, and why `scripts/generate_instruction_files.py` produces skeleton files filled with TODO markers rather than complete, production-ready templates.

If you are an AI model tasked with creating or improving instruction file generation, this document will help you understand:

- **What makes Phase 1 templates easier to generalize**
- **Why Phase 2 and Phase 3 templates resist automation**
- **The specific knowledge gaps that require human expertise**
- **Why TODO markers are a feature, not a bug**

---

## The Current State: What the Generator Does

### What Works Well

The `generate_instruction_files.py` script successfully automates:

1. **Project structure creation**
   - Creates organized directories for multi-phase workflows
   - Generates correctly-named instruction files (e.g., `ROLE_LeadDeveloper_Implementation.md`)
   - Produces supporting documentation (README.md, SESSION_MAPPING.md, USER_REQUEST.md template)

2. **Basic variable substitution**
   - Replaces `[PROJECT_NAME]`, `[PROJECT_PATH]`, `[ROLE_NAME]` with actual values
   - Customizes file paths and working directories
   - Configures phase-specific context

3. **Structural scaffolding**
   - Provides consistent section headers across all roles
   - Ensures all files have standard components (responsibilities, collaboration protocols, completion criteria)
   - Creates phase-specific role mappings

### What Requires Manual Completion

The generator leaves **TODO markers** in critical sections:

```markdown
**Primary Responsibilities:**
- [TODO: Customize for LeadDeveloper role]
- [Add specific responsibilities]
- [Add deliverables]

## Financial Domain Guidance
<!-- TODO: Add domain-specific guidance for financial projects -->

## Python Technology Guidance
<!-- TODO: Add technology-specific patterns and examples -->
```

**Why are there so many TODOs?** Because these sections require **contextual expertise** that cannot be reliably automated without deep knowledge of:
- The specific role's decision-making authority
- Domain-specific constraints and regulations
- Technology stack best practices and anti-patterns
- Project-specific workflow nuances

---

## Why Phase 1 Templates Are Easier to Generalize

### Universal Structure of Requirements Gathering

Phase 1 (Requirements/PRD creation) has a **well-defined, project-agnostic workflow**:

1. **Read USER_REQUEST.md** → Understand the problem
2. **Identify gaps** → Create CLARIFICATION_REQUEST.md if needed
3. **Interview stakeholder** → Exchange via USER_RESPONSE.md
4. **Draft PRD.md** → Document functional/non-functional requirements
5. **Iterate until approved** → Refine based on feedback
6. **Signal [[PROJECT_COMPLETE]]** → Hand off to Phase 2

This workflow is **largely the same** whether you're building:
- A financial reconciliation tool
- A video game
- A data processing pipeline
- A web application

### Why This Works

**1. Requirements Are Domain-Agnostic at High Level**

All projects need to answer the same fundamental questions:
- **What** is the user trying to accomplish? (Problem statement)
- **Who** will use this? (Target users)
- **What** should the system do? (Functional requirements)
- **How well** must it perform? (Non-functional requirements)
- **When** is it successful? (Acceptance criteria)

**2. The PRD Format Is Standardized**

A PRD has consistent sections regardless of project type:
- Problem Statement
- Target Users
- Functional Requirements (FR-1, FR-2, etc.)
- Non-functional Requirements (NFR-1, NFR-2, etc.)
- Success Criteria
- Out of Scope

**3. Role Responsibilities Are Clear and Stable**

- **Product Manager:** Owns PRD, leads clarification, ensures completeness
- **Business Analyst:** Validates technical feasibility, identifies data/domain needs, reviews for gaps

These roles have **well-established patterns** in software development, so their instruction files can be written generically and still be effective.

**4. Domain Adaptation Is Minimal and Stylistic**

The PRD templates include **domain-adaptive guidance**, but it's primarily about:
- **Precision requirements** (financial apps need exact decimal handling)
- **Compliance considerations** (healthcare has HIPAA, finance has audit trails)
- **Terminology** (gaming has "levels" and "players", finance has "transactions" and "accounts")

Critically, **these adaptations don't change the workflow**—they just inform the types of questions to ask and the level of detail required.

### Example: Domain Adaptation in Phase 1

From `ROLE_ProductManager_Requirements.md`:

```markdown
## Domain-Aware Clarification Questions

**For Financial/Accounting Projects:**
- What precision is required? (decimal places, rounding rules)
- Are audit trails needed? (who changed what, when)
- What compliance standards apply? (SOX, GAAP, tax regulations)

**For Gaming Projects:**
- What platform(s)? (PC, mobile, console, web)
- Single-player, multiplayer, or both?
- Real-time or turn-based?
```

Notice: **The questions are different, but the process of asking them is identical.** This makes Phase 1 templates highly generalizable.

---

## Why Phase 2 and Phase 3 Templates Resist Automation

### Phase 2 (Planning/Architecture) Challenges

#### Challenge 1: Technology Stack Determines Everything

Unlike Phase 1 (which is technology-agnostic), Phase 2 decisions are **deeply tied to the tech stack**:

**Example: "How should we structure the project?"**

| Tech Stack | Typical Structure | Key Decisions |
|------------|-------------------|---------------|
| Python CLI | `src/`, `tests/`, `setup.py` | Argparse vs Click? Logging strategy? Config file format? |
| Python + React | `backend/`, `frontend/`, `shared/` | Monorepo or separate repos? REST or GraphQL? State management (Redux, Zustand)? |
| Game (Unity) | `Assets/`, `Scripts/`, `Scenes/` | ECS or MonoBehaviour? Addressables for assets? Multiplayer framework? |
| Data Pipeline | `pipelines/`, `transforms/`, `schemas/` | Airflow? Prefect? Spark? Batch or streaming? |

**Problem:** The generator knows the user selected "Python + React," but it **cannot know**:
- Whether they prefer Redux or Zustand for state management
- If they want REST or GraphQL APIs
- Whether they need containerization (Docker)
- If they require CI/CD pipelines
- What database is appropriate (PostgreSQL, MongoDB, SQLite?)

**Why This Matters:** An Architect AI needs **specific guidance** on these decisions, not generic placeholders. A TODO saying "Add technology-specific patterns" doesn't help the AI make the right architectural choice.

#### Challenge 2: Domain Constraints Are Technical, Not Just Contextual

In Phase 1, domain knowledge helps **ask better questions**. In Phase 2, domain knowledge **constrains technical decisions**.

**Example: Financial Domain in Phase 2**

```markdown
## Financial Domain Architecture Considerations

**Data Precision:**
- Use `decimal.Decimal` in Python, NEVER `float` for monetary values
- Store currency amounts as integers (cents) to avoid floating-point errors
- Validate rounding before calculations (round-half-even for financial compliance)

**Audit Trail Requirements:**
- Every transaction must have immutable log entry (who, what, when)
- Use event sourcing or write-ahead logging
- Consider separate audit database for compliance

**Reconciliation Logic:**
- Implement double-entry bookkeeping (debits = credits)
- Use transactions to ensure atomicity
- Build idempotency for duplicate transaction prevention
```

**Problem:** This is **not domain-agnostic guidance**. It's specific, technical, and wrong choices here lead to **critical bugs** (e.g., floating-point errors causing off-by-one-cent discrepancies in financial reports).

The generator cannot produce this level of detail because it would need to:
1. Know **all** domain-specific architectural patterns (financial, healthcare, gaming, etc.)
2. Keep them **current** (best practices evolve)
3. **Combine** domain + tech stack (financial Python app vs. financial JavaScript app have different patterns)

#### Challenge 3: Project Type Changes the Deliverables

Phase 2's output varies dramatically by project type:

| Project Type | ARCHITECTURE.md Emphasis | PROJECT_TASKS.md Structure |
|--------------|-------------------------|---------------------------|
| CLI Tool | Argument parsing, error handling, config files | Linear task list (parse args → implement commands → add tests) |
| Web Application | API design, database schema, frontend/backend split | Parallel tracks (backend tasks, frontend tasks, integration tasks) |
| Game | Game loop, entity management, asset pipeline | Phase-based (prototype → core mechanics → polish) |
| Data Pipeline | Data flow, transformation logic, scheduling | DAG-based (extract → transform → load → validate) |

**Problem:** The generator would need **different templates for each project type**, and even then, each template would require customization based on the specific requirements from the PRD.

### Phase 3 (Implementation) Challenges

#### Challenge 4: Code Patterns Are Highly Contextual

Phase 3 instruction files should include **concrete code examples** to guide AI developers:

**Example: What a good Phase 3 template should contain:**

```markdown
## Python Best Practices for This Project

**Error Handling:**
✅ **Do:**
```python
def calculate_total(items: list[Item]) -> Decimal:
    """Calculate total with proper error handling."""
    if not items:
        raise ValueError("Cannot calculate total for empty item list")

    total = Decimal('0.00')
    for item in items:
        if item.price < 0:
            raise ValueError(f"Invalid price for {item.name}: {item.price}")
        total += item.price

    return total
```

❌ **Don't:**
```python
def calculate_total(items):
    # No type hints, no validation, no error handling
    return sum(item.price for item in items)
```
```

**Problem:** These examples are **project-specific**:
- The `Item` class structure depends on the PRD
- The validation logic depends on business rules
- The error types depend on the application's error handling strategy

The generator cannot produce these without:
1. Reading and understanding the PRD
2. Knowing the project's coding conventions
3. Inferring the data model from requirements

#### Challenge 5: Common Pitfalls Are Discovered, Not Predicted

One of the most valuable sections in instruction files is **"Common Pitfalls to Avoid"**—but these are based on **experience**, not theory.

**Example from a hypothetical financial CLI tool:**

```markdown
## Common Pitfalls to Avoid

**Floating-Point Arithmetic:**
- ⚠️ Don't use `float` for currency: `total = 10.10 + 20.20  # May equal 30.299999999999997`
- ✅ Do use `Decimal`: `total = Decimal('10.10') + Decimal('20.20')  # Exactly 30.30`

**CSV Parsing:**
- ⚠️ Don't assume all input files are well-formed
- ✅ Do validate row length, handle missing fields, log malformed rows

**Date Handling:**
- ⚠️ Don't mix naive and timezone-aware datetimes
- ✅ Do use UTC internally, convert to local time for display only
```

**Problem:** These pitfalls are **discovered through testing and iteration**:
- A human developer makes the `float` mistake, sees incorrect totals, learns to use `Decimal`
- An AI developer without this guidance will make the same mistake

The generator cannot predict these because:
1. It hasn't run the project yet
2. It doesn't know which mistakes are likely for this specific combination of domain + tech stack + requirements
3. Pitfalls emerge from edge cases in the PRD (e.g., "What if a CSV row has extra commas?")

#### Challenge 6: Task Decomposition Requires PRD Understanding

Phase 3's `PROJECT_TASKS.md` should be a **granular, ordered list** derived from the PRD:

**Example: From PRD to Tasks**

**PRD Requirement:**
```markdown
FR-1: The system shall allow users to upload a CSV file containing transactions
      and calculate the total amount spent per category.
```

**Corresponding PROJECT_TASKS.md:**
```markdown
1. **CSV Upload Handling**
   - [ ] Create `upload_csv(filepath: Path) -> list[Transaction]` function
   - [ ] Validate CSV headers match expected format
   - [ ] Handle FileNotFoundError, PermissionError
   - Test: Upload valid CSV, verify Transaction objects created

2. **Transaction Parsing**
   - [ ] Implement `Transaction` dataclass (date, amount, category, description)
   - [ ] Parse each CSV row into Transaction
   - [ ] Handle missing/invalid fields gracefully
   - Test: Parse CSV with edge cases (missing category, negative amount)

3. **Category Aggregation**
   - [ ] Create `aggregate_by_category(transactions: list[Transaction]) -> dict[str, Decimal]`
   - [ ] Sum amounts per category
   - [ ] Handle uncategorized transactions (default to "Uncategorized")
   - Test: Aggregate sample transactions, verify totals

4. **Output Formatting**
   - [ ] Display results in table format (use `tabulate` library)
   - [ ] Sort categories by total (descending)
   - Test: Format sample output, verify sorting and alignment
```

**Problem:** This task breakdown requires:
1. **Reading the PRD** and understanding FR-1
2. **Making design decisions** (What fields should `Transaction` have? Should we use a library for CSV parsing or built-in `csv`?)
3. **Ordering tasks by dependency** (Can't aggregate before parsing)
4. **Defining test cases** based on requirement details

The generator cannot do this because **it hasn't read the PRD**—the PRD doesn't exist until Phase 1 completes.

---

## The Catch-22 of Automation

Here's the fundamental problem:

### To Generate Complete Phase 2/3 Templates, You Need:

1. **The PRD** (output of Phase 1) → Defines requirements that inform architecture and tasks
2. **Architectural decisions** (made during Phase 2) → Determines task structure
3. **Code patterns** (emerge during Phase 3) → Informs best practices and pitfalls

### But the Generator Runs BEFORE Phase 1 Starts

When the user runs `generate_instruction_files.py`, they haven't yet:
- Written USER_REQUEST.md
- Created the PRD
- Made architectural decisions
- Written any code

**Therefore, the generator cannot:**
- Customize Phase 2 templates based on PRD requirements (PRD doesn't exist)
- Customize Phase 3 templates based on architectural decisions (architecture not yet designed)
- Provide project-specific code examples (code not yet written)

### The Only Two Options

**Option 1: Generate Generic Skeletons with TODOs** (Current Approach)
- ✅ Provides structure and consistency
- ✅ Ensures all necessary sections are present
- ❌ Requires significant manual customization
- ❌ AI models executing these templates still need human guidance

**Option 2: Wait Until Each Phase Completes, Then Generate Next Phase's Templates**
- ✅ Could use PRD to inform Phase 2 templates
- ✅ Could use ARCHITECTURE.md to inform Phase 3 templates
- ❌ Requires AI to generate instruction files (meta-complexity)
- ❌ Still cannot predict "common pitfalls" without running the project

---

## What the Generator Does Well (and Should Continue Doing)

Despite these challenges, the generator provides **significant value**:

### 1. Enforces Consistency

All generated files have:
- Security boundaries (project directory restrictions)
- Response delimiter protocols (for orchestrated chat)
- Role-specific context (phase, collaborators, completion criteria)
- Standard section structure (responsibilities, workflows, collaboration protocols)

This ensures that **human customization happens within a proven framework**, rather than inventing structure from scratch.

### 2. Handles Boilerplate Variable Substitution

Replacing `[PROJECT_PATH]`, `[ROLE_NAME]`, etc. is tedious and error-prone when done manually. The generator handles this reliably.

### 3. Creates Correct File Topology

Naming files consistently (`ROLE_LeadDeveloper_Implementation.md`) and organizing them in logical directories (`templates/projects/MyProject/`) prevents confusion and enables SESSION_MAPPING.md to reference files correctly.

### 4. Generates Useful Supporting Documentation

- **README.md:** Explains the project's workflow and roles
- **SESSION_MAPPING.md:** Shows exactly which files to use for each orchestration session
- **USER_REQUEST.md template:** Guides users in writing effective requests
- **project_config.json:** Preserves generation parameters for future reference

### 5. Reduces Time to First Draft

Even with TODOs, a generated skeleton is **much faster** than writing 6-12 instruction files from scratch. The user can focus on **adding domain/tech knowledge** rather than **creating structure**.

---

## Why TODOs Are a Feature, Not a Bug

### The TODO Philosophy

TODOs in generated files serve as **explicit prompts** for human expertise:

```markdown
## Financial Domain Guidance
<!-- TODO: Add domain-specific guidance for financial projects -->
```

This TODO is not a failure—it's an **intentional placeholder** that tells the user:
> "This section requires your financial domain expertise. The generator cannot know whether your project needs SOX compliance, GAAP standards, or specific audit trail requirements. Fill this in based on your project's actual needs."

### Why Blank Sections Are Worse

Consider the alternative—leaving sections blank or omitting them entirely:

**Without TODO:**
```markdown
## Financial Domain Guidance

```

**Problem:** The user might **not notice** this section exists, and the AI model won't receive critical guidance. The TODO forces acknowledgment.

**Omitting Section Entirely:**

**Problem:** Even worse—the user might not realize they **should** provide domain guidance. The section's presence (even with TODO) serves as a **checklist** of what complete instruction files need.

### TODOs as Quality Gates

TODOs prevent premature execution:
- If a user runs an orchestration session with un-customized templates, the AI models will encounter TODOs and can **alert the user** that the templates are incomplete
- This prevents wasted time on sessions where the AI lacks necessary context

---

## TODO Taxonomy: Who Fills What and When

Not all TODOs are created equal. Understanding which TODOs require which expertise helps assign ownership and prioritize completion.

### Category 1: Domain Expertise TODOs

**Who fills these:** Domain expert, business stakeholder, or specialized consultant

**When to fill:** Before Phase 1 begins (for PRD templates) or during template customization

**Examples:**
```markdown
## Financial Domain Guidance
<!-- TODO: Add domain-specific guidance for financial projects -->
```

**What to add:**
- Regulatory requirements (SOX, GAAP, HIPAA, etc.)
- Industry-standard data precision rules (decimal places, rounding)
- Compliance constraints (audit trails, data retention)
- Domain terminology and conventions

**Impact if left unfilled:** AI models may miss critical compliance requirements or use incorrect patterns (e.g., `float` instead of `Decimal` for currency)

---

### Category 2: Technology Stack TODOs

**Who fills these:** Lead developer, tech lead, or architect familiar with chosen technologies

**When to fill:** After project config is known (tech stack selected), ideally before Phase 2

**Examples:**
```markdown
## Python Technology Guidance
<!-- TODO: Add technology-specific patterns and examples -->
```

**What to add:**
- Framework-specific best practices (FastAPI vs Flask, React vs Vue)
- Error handling patterns for the tech stack
- Testing strategies (pytest, Jest, unittest)
- Code organization conventions (where to put models, controllers, utils)
- Dependency management approach

**Impact if left unfilled:** AI models may use outdated patterns or make poor technology choices (e.g., picking libraries incompatible with the stack)

---

### Category 3: Authority and Decision-Making TODOs

**Who fills these:** Project manager or team lead based on team structure

**When to fill:** During template customization, before orchestration sessions begin

**Examples:**
```markdown
**Decision Authority:** [TODO: Define authority level]
```

```markdown
**Decision Making:**
- You can decide autonomously: [TODO: List autonomous decisions]
- Requires {other_role_name} consensus: [TODO: List collaborative decisions]
```

**What to add:**
- Which role has final say on architecture decisions
- Which decisions require stakeholder approval
- Which decisions can be made autonomously by AI models
- Conflict resolution protocol (who breaks ties)

**Impact if left unfilled:** AI models may defer excessively to each other, stalling progress, or make decisions that should require human approval

---

### Category 4: Workflow and Process TODOs

**Who fills these:** Project manager or process owner

**When to fill:** During template customization

**Examples:**
```markdown
## Workflow Phases

**Phase 1: [TODO: Activity Name]** (Turn 1-3)
- [ ] [TODO: Add steps]
- Exit criteria: [TODO: Define]
```

**What to add:**
- Specific activities for each workflow phase
- Turn-by-turn breakdown (what happens in turns 1-3, 4-6, etc.)
- Exit criteria for each phase (when to move to next phase)
- Checkpoints for human review

**Impact if left unfilled:** AI models lack structure and may skip important steps or proceed without necessary validation

---

### Category 5: Example and Pattern TODOs (Auto-Fillable)

**Who fills these:** Can be automatically filled by staged generation OR manually by developers

**When to fill:** After Phase 1 (using PRD) or Phase 2 (using ARCHITECTURE), or manually during customization

**Examples:**
```markdown
**Input Artifacts:**
- [TODO: List required input files]

**Output Artifacts:**
- [TODO: List expected output files]
```

```markdown
## Common Pitfalls to Avoid
<!-- TODO: Add project-specific anti-patterns -->
```

**What to add:**
- Specific file names from PRD or ARCHITECTURE (e.g., "Read PRD.md for requirements")
- Data model examples from the PRD
- Code patterns based on architectural decisions
- Known edge cases from requirements

**Impact if left unfilled:** AI models lack concrete examples and may create incorrect file names or data structures

**Note:** These are candidates for **staged generation** (see next section) because they can be partially automated once PRD/ARCHITECTURE exist.

---

### TODO Completion Checklist

Before running an orchestration session, verify:

- [ ] **Domain TODOs filled** → Expert has added industry-specific guidance
- [ ] **Tech Stack TODOs filled** → Developer has added framework patterns
- [ ] **Authority TODOs filled** → PM has defined decision-making rules
- [ ] **Workflow TODOs filled** → PM has structured the phase activities
- [ ] **Example TODOs filled or acceptable** → Either staged generation ran OR examples added manually OR team agrees to fill during execution

**Priority:**
- **Critical:** Domain, Tech Stack (missing these leads to incorrect implementations)
- **High:** Authority, Workflow (missing these leads to stalled or disorganized sessions)
- **Medium:** Examples (can be filled iteratively during execution if needed)

---

## Staged Generation: Solving the Catch-22

The "Catch-22" described earlier (generator runs before PRD exists) is not insurmountable. The solution is **staged generation**—running the generator multiple times as artifacts become available.

### The Staged Generation Workflow

**Stage 1: Initial Generation (Before Phase 1)**

```bash
python scripts/generate_instruction_files.py
```

**Generates:**
- Phase 1 instruction files (Requirements/PRD)
- Phase 2 instruction files (with TODOs)
- Phase 3 instruction files (with TODOs)
- Supporting docs (README, SESSION_MAPPING, USER_REQUEST template)

**User actions:**
- Customize Phase 1 templates (fill Domain, Tech Stack, Authority TODOs)
- Create USER_REQUEST.md
- Run Phase 1 orchestration session

**Output:** PRD.md

---

**Stage 2: Phase 2 Refinement (After Phase 1 Completes)**

```bash
python scripts/generate_instruction_files.py \
  --refine \
  --phase 2 \
  --prd-file ./PRD.md
```

**What this does:**
- Reads PRD.md to extract:
  - Functional requirements → Informs architecture priorities
  - Data models → Adds to ARCHITECTURE.md template
  - Non-functional requirements → Guides technology choices
  - Success criteria → Becomes testing strategy
- Updates Phase 2 instruction files by:
  - Filling "Input Artifacts" TODOs with actual file names from PRD
  - Adding PRD-derived examples to workflow phases
  - Suggesting architectural patterns based on requirements
  - **Preserving** any human customizations already made

**User actions:**
- Review auto-filled content
- Fill remaining Domain/Tech TODOs specific to architecture decisions
- Run Phase 2 orchestration session

**Output:** ARCHITECTURE.md, PROJECT_TASKS.md

---

**Stage 3: Phase 3 Refinement (After Phase 2 Completes)**

```bash
python scripts/generate_instruction_files.py \
  --refine \
  --phase 3 \
  --architecture-file ./ARCHITECTURE.md \
  --tasks-file ./PROJECT_TASKS.md
```

**What this does:**
- Reads ARCHITECTURE.md to extract:
  - Component structure → Informs code organization
  - Technology choices → Adds framework-specific examples
  - Data models → Creates example class definitions
  - Integration points → Highlights testing needs
- Reads PROJECT_TASKS.md to extract:
  - Task list → Becomes implementation checklist
  - Dependencies → Informs workflow order
- Updates Phase 3 instruction files by:
  - Filling "Common Pitfalls" with tech-stack-specific anti-patterns
  - Adding code examples based on chosen architecture
  - Creating task-specific workflow phases
  - **Preserving** human customizations

**User actions:**
- Review auto-filled content
- Add project-specific code examples if needed
- Run Phase 3 orchestration session

**Output:** Working code

---

### Benefits of Staged Generation

1. **Reduces TODO burden:** Category 5 TODOs (examples, patterns) are largely auto-filled
2. **Context-aware templates:** Phase 2/3 templates reference actual project artifacts
3. **Maintains flexibility:** Humans still fill critical Domain/Tech TODOs; automation handles boilerplate
4. **Safe refinement:** `--refine` mode preserves existing customizations, only fills TODOs

### What Staged Generation Cannot Do

Even with staged generation, humans must still provide:
- **Domain expertise:** Compliance rules, industry regulations, business logic constraints
- **Technology expertise:** Current best practices, framework-specific patterns, security considerations
- **Project judgment:** Which requirements are critical vs. nice-to-have, acceptable trade-offs

**Why:** These require deep contextual knowledge that cannot be reliably extracted from PRD/ARCHITECTURE text alone.

---

## What the Generator Actually Produces: A Concrete Example

To make the challenges concrete, here's a side-by-side comparison of what `generate_instruction_files.py` currently outputs versus what a complete, customized template looks like.

### Generated Template (Current Output)

This is what `scripts/generate_instruction_files.py` produces (from `_get_role_template()` function, lines 502-575):

```markdown
## Your Role: LeadDeveloper (Implementation Phase)

**Primary Responsibilities:**
- [TODO: Customize for LeadDeveloper role]
- [Add specific responsibilities]
- [Add deliverables]

**Secondary Responsibilities:**
- [TODO: Add supporting activities]

**Team Position:**
- Reports to: Project Stakeholder
- Collaborates with: CodeReviewer
- Decision Authority: **LEAD ROLE** - [TODO: Define authority level]

## Project Context

**Phase**: Implementation
**Working Directory:** /home/user/Projects/MyFinancialApp

**Input Artifacts:**
- [TODO: List required input files]

**Output Artifacts:**
- [TODO: List expected output files]

**Success Criteria:**
- [TODO: Define completion criteria]

## Workflow Phases

**Phase 1: [TODO: Activity Name]** (Turn 1-3)
- [ ] [TODO: Add steps]
- Exit criteria: [TODO: Define]

## Financial Domain Guidance

<!-- TODO: Add domain-specific guidance for financial projects -->

## Python Technology Guidance

<!-- TODO: Add technology-specific patterns and examples -->

## Collaboration Protocols

**With CodeReviewer:**
- They focus on: [TODO: Define their focus]
- You focus on: [TODO: Define your focus]
- Defer to them on: [TODO: When to follow their lead]
- Lead on: [TODO: When you have final say]

**Decision Making:**
- You can decide autonomously: [TODO: List autonomous decisions]
- Requires CodeReviewer consensus: [TODO: List collaborative decisions]

## Common Pitfalls to Avoid

**[Category]:**
- ⚠️ Don't [TODO: Add anti-patterns]
- ✅ Do [TODO: Add best practices]

## Definition of Done

This implementation phase is complete when:
- [ ] [TODO: Add specific completion criteria]
- [ ] CodeReviewer has reviewed and approved
- [ ] Both team members signal [[PROJECT_COMPLETE]]

**You may signal [[PROJECT_COMPLETE]] when:**
1. [TODO: Add condition]
2. CodeReviewer confirms agreement
3. All deliverables are complete
```

### Complete Template (After Human Customization)

This is what the template looks like after human experts fill the TODOs (similar to `templates/prd_universal/ROLE_ProductManager_Requirements.md`):

```markdown
## Your Role: LeadDeveloper (Implementation Phase)

**Primary Responsibilities:**
- Implement all features defined in PRD.md and ARCHITECTURE.md
- Write unit and integration tests for all components
- Follow Python best practices and project coding standards
- Collaborate with CodeReviewer on design decisions and code quality

**Secondary Responsibilities:**
- Document code with clear docstrings and comments
- Update PROJECT_TASKS.md as tasks are completed
- Flag technical risks or blockers to stakeholder

**Team Position:**
- Reports to: Project Stakeholder
- Collaborates with: CodeReviewer
- Decision Authority: **LEAD ROLE** - Final say on implementation details (variable names, function structure, internal algorithms). Requires CodeReviewer consensus on public APIs, security patterns, and performance-critical code.

## Project Context

**Phase**: Implementation
**Working Directory:** /home/user/Projects/MyFinancialApp

**Input Artifacts:**
- PRD.md (functional/non-functional requirements)
- ARCHITECTURE.md (system design, component structure)
- PROJECT_TASKS.md (ordered task list with dependencies)

**Output Artifacts:**
- Source code files (src/reconciliation.py, src/models.py, etc.)
- Test files (tests/test_reconciliation.py, etc.)
- README.md (usage instructions)

**Success Criteria:**
- All tasks in PROJECT_TASKS.md marked complete
- All tests pass (pytest shows 100% of tests passing)
- Code review approved by CodeReviewer
- No critical bugs remaining

## Workflow Phases

**Phase 1: Environment Setup** (Turn 1-2)
- [ ] Create project structure (src/, tests/, docs/)
- [ ] Set up virtual environment and install dependencies
- [ ] Configure pytest and linting tools
- Exit criteria: Can run `pytest` successfully (even with 0 tests)

**Phase 2: Core Implementation** (Turn 3-8)
- [ ] Implement data models (Transaction, Account classes)
- [ ] Implement reconciliation logic
- [ ] Write unit tests for each component
- Exit criteria: All FR requirements implemented and tested

**Phase 3: Integration and Polish** (Turn 9-10)
- [ ] Integration testing (end-to-end workflows)
- [ ] Error handling and edge cases
- [ ] Documentation and README
- Exit criteria: All tests pass, documentation complete

## Financial Domain Guidance

**Data Precision:**
- ALWAYS use `decimal.Decimal` for monetary amounts, NEVER `float`
- Store currency as integers (cents) in database to avoid floating-point errors
- Example:
  ```python
  from decimal import Decimal

  # ✅ Correct
  total = Decimal('10.50') + Decimal('20.30')  # Exactly 30.80

  # ❌ Wrong
  total = 10.50 + 20.30  # May be 30.799999999999997
  ```

**Audit Trails:**
- Every transaction must have an immutable log entry (who, what, when)
- Use event sourcing pattern or write-ahead logging
- Never delete records—mark as void/cancelled instead

**Reconciliation Logic:**
- Implement double-entry bookkeeping (debits must equal credits)
- Use database transactions to ensure atomicity
- Build idempotency (same transaction processed twice has no additional effect)

## Python Technology Guidance

**Error Handling:**
```python
# ✅ Do: Specific exceptions with context
def load_transactions(filepath: Path) -> list[Transaction]:
    if not filepath.exists():
        raise FileNotFoundError(f"Transaction file not found: {filepath}")

    try:
        with open(filepath) as f:
            return parse_transactions(f)
    except ValueError as e:
        raise ValueError(f"Invalid transaction format in {filepath}: {e}")

# ❌ Don't: Bare excepts or generic errors
def load_transactions(filepath):
    try:
        with open(filepath) as f:
            return parse_transactions(f)
    except:
        return []  # Silent failure
```

**Testing:**
```python
# ✅ Do: Test edge cases
def test_reconciliation_with_negative_amounts():
    transactions = [
        Transaction(amount=Decimal('-50.00'), category='refund'),
        Transaction(amount=Decimal('100.00'), category='purchase'),
    ]
    result = reconcile(transactions)
    assert result.total == Decimal('50.00')

# ❌ Don't: Only test happy path
def test_reconciliation():
    transactions = [Transaction(amount=Decimal('100.00'))]
    assert reconcile(transactions).total == Decimal('100.00')
```

## Collaboration Protocols

**With CodeReviewer:**
- They focus on: Code quality, security, performance, maintainability
- You focus on: Implementation, feature completion, test coverage
- Defer to them on: Security patterns (input validation, SQL injection prevention), performance-critical algorithms
- Lead on: Internal implementation details, variable naming, code organization

**Decision Making:**
- You can decide autonomously: Function names, local variable names, internal helper functions, test organization
- Requires CodeReviewer consensus: Public API design, security-sensitive code (authentication, data validation), performance-critical algorithms, third-party library choices

## Common Pitfalls to Avoid

**Floating-Point Arithmetic:**
- ⚠️ Don't use `float` for currency: `total = 10.10 + 20.20  # May equal 30.299999999999997`
- ✅ Do use `Decimal`: `total = Decimal('10.10') + Decimal('20.20')  # Exactly 30.30`

**CSV Parsing:**
- ⚠️ Don't assume all input files are well-formed
- ✅ Do validate row length, handle missing fields, log malformed rows without crashing

**Date Handling:**
- ⚠️ Don't mix naive and timezone-aware datetimes
- ✅ Do use UTC internally, convert to local time for display only

**Error Messages:**
- ⚠️ Don't expose internal paths or stack traces to users
- ✅ Do provide helpful, actionable error messages ("File not found: transactions.csv. Ensure the file exists in /path/to/dir")

## Definition of Done

This implementation phase is complete when:
- [ ] All tasks in PROJECT_TASKS.md are marked complete
- [ ] All PRD functional requirements (FR-1 through FR-5) are implemented
- [ ] All tests pass (pytest shows 100% pass rate)
- [ ] Code review by CodeReviewer is complete and approved
- [ ] README.md contains usage instructions and examples
- [ ] No critical or high-priority bugs remain
- [ ] Both team members signal [[PROJECT_COMPLETE]]

**You may signal [[PROJECT_COMPLETE]] when:**
1. All tasks are checked off in PROJECT_TASKS.md
2. `pytest` runs with no failures
3. CodeReviewer has approved the code
4. You've tested the application end-to-end successfully
5. CodeReviewer confirms agreement
```

### Key Differences

| Section | Generated (TODOs) | Complete (Customized) | TODO Category |
|---------|-------------------|------------------------|---------------|
| **Primary Responsibilities** | Generic placeholders | Specific deliverables (implement features, write tests, follow standards) | Workflow (Cat. 4) |
| **Decision Authority** | [TODO: Define authority level] | Detailed rules (final say on implementation, consensus on APIs) | Authority (Cat. 3) |
| **Input/Output Artifacts** | [TODO: List files] | Actual file names (PRD.md, ARCHITECTURE.md, src/reconciliation.py) | Examples (Cat. 5) - Auto-fillable |
| **Workflow Phases** | [TODO: Activity Name] | Specific phases (Environment Setup, Core Implementation, Integration) with turn counts | Workflow (Cat. 4) |
| **Domain Guidance** | <!-- TODO --> | Detailed financial patterns (Decimal usage, audit trails, double-entry bookkeeping) | Domain (Cat. 1) - Requires expert |
| **Technology Guidance** | <!-- TODO --> | Python code examples (error handling, testing patterns) | Tech Stack (Cat. 2) - Requires expert |
| **Common Pitfalls** | [TODO: Add anti-patterns] | Specific examples (float vs Decimal, CSV validation, timezone handling) | Examples (Cat. 5) - Partially auto-fillable |

### Which TODOs Can Staged Generation Fill?

With **Stage 2 refinement** (after PRD.md exists):
- ✅ **Input/Output Artifacts:** Extract from PRD sections ("PRD.md FR-1 requires CSV upload" → "Input: transactions.csv")
- ✅ **Workflow Phases:** Derive from PRD structure ("Implement FR-1, FR-2, FR-3" → Create phases)
- ✅ **Success Criteria:** Copy from PRD success criteria section
- ⚠️ **Common Pitfalls:** Partially (can add generic Python pitfalls, but not financial-specific ones without domain knowledge)

With **Stage 3 refinement** (after ARCHITECTURE.md exists):
- ✅ **Technology Guidance:** Extract architectural decisions ("Use FastAPI" → Add FastAPI examples)
- ✅ **Code Examples:** Generate based on data models in ARCHITECTURE ("Transaction class has amount, date, category" → Create example code)
- ⚠️ **Common Pitfalls:** Add tech-stack-specific ones (FastAPI async patterns), but not domain-specific

**Still requires human expert:**
- ❌ **Domain Guidance:** Cannot auto-generate "use Decimal not float" without financial expertise
- ❌ **Authority Rules:** Cannot infer who has final say without knowing team structure
- ❌ **Deep Pitfalls:** Cannot predict "timezone-aware datetime" issues without experience

---

## Additional Automation Opportunities

Beyond staged generation (which is already planned), further improvements could include:

### 1. Knowledge Base of Domain + Tech Stack Patterns

Build a library of reusable guidance modules:

```
knowledge_base/
├── domains/
│   ├── financial.md
│   ├── gaming.md
│   ├── healthcare.md
├── tech_stacks/
│   ├── python.md
│   ├── python_react.md
│   ├── unity_csharp.md
├── project_types/
│   ├── cli.md
│   ├── webapp.md
│   ├── data_pipeline.md
```

The generator could **compose** templates by combining:
- `domains/financial.md` + `tech_stacks/python.md` + `project_types/cli.md` → Financial Python CLI instruction files

**Challenge:**
- Maintaining dozens of domain/tech/project-type combinations
- Keeping them current as best practices evolve
- Handling conflicts (what if domain guidance contradicts tech stack guidance?)

### 2. Example-Based Learning

Allow users to **contribute back** completed templates:

- User completes a financial Python CLI project
- User's customized instruction files are saved to `knowledge_base/examples/financial_python_cli/`
- Next user creating a similar project can **clone and adapt** these proven templates instead of starting from scratch

**Challenge:**
- Example quality varies (not all users write good templates)
- Examples become outdated (Python 3.9 patterns vs. Python 3.13)
- Privacy concerns (templates might reveal proprietary domain logic)

---

## Recommended Approach: Staged Generation + Human Expertise

The optimal strategy combines **staged generation** (automated refinement as artifacts become available) with **human expertise** (domain and tech knowledge that cannot be automated).

### What Staged Generation Automates

✅ **Initial scaffolding** → All files have consistent structure (Stage 1)
✅ **Variable substitution** → Project paths, names, roles (Stage 1)
✅ **File organization** → Correct naming, directory structure (Stage 1)
✅ **Supporting docs** → README, SESSION_MAPPING, USER_REQUEST template (Stage 1)
✅ **Base protocols** → Security boundaries, response delimiters, completion signals (Stage 1)
✅ **PRD-derived examples** → Input/output artifacts, workflow phases, success criteria (Stage 2)
✅ **Architecture-derived examples** → Code patterns, component structure, testing strategy (Stage 3)

### What Requires Human Expertise

❌ **Domain-specific guidance** → Requires expert knowledge (financial regulations, healthcare compliance, gaming mechanics)
❌ **Technology-specific patterns** → Requires current best practices (React state management, Python async patterns)
❌ **Authority and decision-making rules** → Requires understanding of team structure and project governance
❌ **Deep common pitfalls** → Requires experience (learned through iteration and debugging)
❌ **Domain-tech integration** → Requires knowing how domain constraints affect technology choices (e.g., "financial apps must use Decimal")

### Why This Works

This division **respects the knowledge boundary** while **maximizing automation**:
- **Stage 1 (initial):** Generator handles structure and boilerplate
- **Stage 2 (after PRD):** Generator extracts project-specific context from requirements
- **Stage 3 (after ARCHITECTURE):** Generator adds tech-stack-specific examples from design decisions
- **Human at all stages:** Provides domain expertise, tech expertise, and governance rules

**Result:** Category 5 TODOs (examples, patterns) are largely auto-filled, while Category 1-4 TODOs (domain, tech stack, authority, workflow) receive human expertise where it matters most

---

## Implications for AI Models

If you are an AI model reading this document, understand:

### 1. Incomplete Templates Are Expected

If you encounter a TODO in your instruction file, this is **intentional**. It means:
- The generator recognized that this section requires context it didn't have
- Your human supervisor should have customized this section before running the session
- If the TODO remains, **ask the user to complete it** before proceeding

### 2. Don't Invent Context

When you see:
```markdown
## Financial Domain Guidance
<!-- TODO: Add domain-specific guidance for financial projects -->
```

**Do NOT** try to fill this in based on general knowledge. The specific project may have unique requirements:
- Different precision rules than standard financial apps
- Different compliance needs (international vs. US)
- Different audit trail requirements

Instead: **Flag this to the user** and ask for clarification.

### 3. Use TODOs as Collaboration Triggers

If you're an AI model in a multi-model orchestration session:
- TODOs are opportunities to **ask your teammate** if they have context
- If neither of you has the context, **ask the human stakeholder**
- Document the answer in MessageBoard.md so future sessions can reference it

### 4. Distinguish Structural vs. Contextual TODOs

**Structural TODO (minor):**
```markdown
**Decision Making:**
- You can decide autonomously: [TODO: List autonomous decisions]
```

This can often be **inferred from role definition**. If you're the Lead role, you likely can decide on implementation details autonomously.

**Contextual TODO (critical):**
```markdown
## Common Pitfalls to Avoid
<!-- TODO: Add project-specific anti-patterns -->
```

This **cannot be inferred**—it requires project experience or domain knowledge.

Flag contextual TODOs as blockers; try to work around structural TODOs if possible.

---

## Conclusion

The `generate_instruction_files.py` script is **not incomplete**—it's **appropriately scoped for Stage 1**. It automates what can be reliably automated before any project artifacts exist and clearly marks what requires either human expertise or later refinement stages.

### The Core Insight

**Phase 1 templates work universally because requirements gathering is a universal process.**

**Phase 2 and 3 templates benefit from staged generation** because planning and implementation are contextual activities that depend on:
- The specific requirements **(available after Phase 1 → enables Stage 2 refinement)**
- The chosen architecture **(available after Phase 2 → enables Stage 3 refinement)**
- Domain expertise **(always requires human expert)**
- Technology expertise **(always requires human expert)**
- The project's code patterns **(emerge during Phase 3, inform future iterations)**

### The Implemented Path Forward

**Staged generation is now the recommended workflow:**

1. **Stage 1 (Initial):** Run generator to create structure and Phase 1 templates
2. **Human customization:** Fill Category 1-4 TODOs (domain, tech, authority, workflow)
3. **Stage 2 (After PRD):** Run `--refine --phase 2 --prd-file PRD.md` to auto-fill examples
4. **Human review:** Validate auto-filled content, add remaining domain/tech context
5. **Stage 3 (After ARCHITECTURE):** Run `--refine --phase 3 --architecture-file ARCHITECTURE.md`
6. **Human finalization:** Add final project-specific examples and pitfalls

**Even with staged generation, human expertise remains essential** because:
- Domain knowledge is deep and nuanced (cannot be extracted from PRD text alone)
- Technology best practices evolve (requires current practitioner knowledge)
- Every project has unique constraints (cannot be predicted from templates)

### For Users: The Staged Generation Workflow

**Stage 1: Before Phase 1**
```bash
python scripts/generate_instruction_files.py
```
- Review generated templates
- Fill **Domain TODOs** (Cat. 1) - Compliance, regulations, domain patterns
- Fill **Tech Stack TODOs** (Cat. 2) - Framework patterns, best practices
- Fill **Authority TODOs** (Cat. 3) - Decision-making rules
- Fill **Workflow TODOs** (Cat. 4) - Phase structure, turn breakdowns
- Run Phase 1 orchestration → Produces PRD.md

**Stage 2: After Phase 1**
```bash
python scripts/generate_instruction_files.py --refine --phase 2 --prd-file ./PRD.md
```
- Generator auto-fills **Example TODOs** (Cat. 5) from PRD
- Review auto-generated content for accuracy
- Fill any remaining domain/tech TODOs specific to architecture
- Run Phase 2 orchestration → Produces ARCHITECTURE.md, PROJECT_TASKS.md

**Stage 3: After Phase 2**
```bash
python scripts/generate_instruction_files.py --refine --phase 3 \
  --architecture-file ./ARCHITECTURE.md \
  --tasks-file ./PROJECT_TASKS.md
```
- Generator auto-fills code examples, testing patterns, workflow phases
- Add final project-specific pitfalls and patterns
- Run Phase 3 orchestration → Produces working code

**Key principle:** Don't be discouraged by Stage 1 TODOs—many will be auto-filled in Stages 2 and 3

### For AI Models

When you execute instruction files with TODOs:

**Understand the TODO category:**
- **Category 1 (Domain):** Critical blocker—ask user for domain expertise
- **Category 2 (Tech Stack):** Critical blocker—ask user for tech patterns
- **Category 3 (Authority):** High priority—ask who has decision rights
- **Category 4 (Workflow):** High priority—ask for phase structure
- **Category 5 (Examples):** Medium priority—may be fillable from PRD/ARCHITECTURE if available, otherwise ask

**Actions to take:**
- **Flag critical TODOs** (Cat. 1-2) to the user immediately—cannot proceed without domain/tech knowledge
- **Ask for clarification** rather than inventing context
- **Check if Stage 2/3 refinement ran** —if templates still have Cat. 5 TODOs, suggest user run `--refine`
- **Document answers** in MessageBoard.md so future sessions can reference them
- **Collaborate with teammate**—they may have the context you're missing

**Remember:** Staged generation fills many TODOs automatically. If you see excessive TODOs in Phase 2/3 templates, the user may have skipped refinement stages.
