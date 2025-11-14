# Instruction File Creation Guide

**Version**: 1.0
**Last Updated**: 2025-11-13
**Purpose**: Guide for creating AI model instruction files for Orchestrator multi-session workflows

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [The Three-Phase Workflow](#the-three-phase-workflow)
4. [Instruction File Anatomy](#instruction-file-anatomy)
5. [Creating New Instruction Files](#creating-new-instruction-files)
6. [Role Definition Guidelines](#role-definition-guidelines)
7. [Authority Hierarchy](#authority-hierarchy)
8. [Best Practices](#best-practices)
9. [Common Patterns](#common-patterns)
10. [Examples and Templates](#examples-and-templates)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The Orchestrator system uses a **multi-session, role-based** approach to AI collaboration. Instead of one AI trying to do everything, we break complex projects into **three phases** with **specialized roles** in each phase. Each AI agent receives a detailed instruction file that defines their role, responsibilities, and collaboration protocols.

### Why This Approach?

**Benefits**:
- **Separation of Concerns**: Requirements → Planning → Implementation
- **Quality Through Specialization**: Each AI focuses on what it does best
- **Iterative Refinement**: Each phase validates and improves on the previous
- **Parallel Work**: Multiple AIs can work simultaneously in implementation
- **Clear Handoffs**: Well-defined artifacts pass between phases

**Proven Results**:
- 30-45 turns for complete project (vs. 100+ in unstructured approaches)
- Higher quality requirements and planning
- Fewer implementation bugs due to thorough planning
- Clear audit trail and documentation

---

## Core Concepts

### Sessions

A **session** is a collaborative discussion between 2-4 AI agents working toward a specific deliverable. Sessions are isolated from each other - they don't share memory or context beyond the artifacts they produce.

**Session Structure**:
- **Input**: Documents from previous session (or user request)
- **Participants**: 2-4 AI agents with specific roles
- **Process**: Turn-based discussion with response delimiters
- **Output**: Specific artifacts (PRD, task list, code, etc.)
- **Completion**: Signaled when agents reach consensus via `[[PROJECT_COMPLETE]]`

### Roles

A **role** defines what an AI agent is responsible for in a session. Roles have:
- **Primary responsibilities**: Core duties they own
- **Secondary responsibilities**: Supporting activities
- **Decision authority**: What they can decide autonomously vs. collaboratively
- **Collaboration protocols**: How they work with other roles

**Example Roles**:
- Phase 1: Product Manager, Business Analyst, UX Designer
- Phase 2: Engineering Manager, Technical Lead, Full Stack Architect
- Phase 3: Lead Developer, Code Reviewer, QA Engineer

### Instruction Files

An **instruction file** is a markdown document that gets prepended to an AI's system prompt. It contains:
1. **Security boundaries** (mandatory template)
2. **Response delimiters** (mandatory protocol)
3. **Role definition** and responsibilities
4. **Workflow phases** specific to this session
5. **Collaboration protocols** with other roles
6. **Domain-specific guidance** for the task at hand

---

## The Three-Phase Workflow

This is the **default pattern** for Orchestrator projects. It can be extended, but three phases is the proven baseline.

### Phase 1: Requirements & PRD Creation

**Goal**: Convert user needs into comprehensive Product Requirements Document

**Typical Roles**:
- **Product Manager** (lead): User perspective, problem definition, scope
- **Business Analyst** (support): Technical details, validation rules, edge cases
- **UX Designer** (optional): User experience, interface design

**Key Activities**:
- Analyze stakeholder input
- Ask clarifying questions if needed
- Define clear, testable requirements
- Document assumptions and constraints
- Identify edge cases and error scenarios

**Outputs**:
- `PRD.md` - Product Requirements Document
- OR `CLARIFICATION_REQUEST.md` - Questions for stakeholder

**Success Criteria**:
- Clear problem statement
- All inputs and outputs defined
- Edge cases identified
- Acceptance criteria specified
- Both agents signal `[[PROJECT_COMPLETE]]`

**Typical Duration**: 6-15 turns (including clarifications)

---

### Phase 2: Planning & Task Decomposition

**Goal**: Break PRD into actionable implementation plan

**Typical Roles**:
- **Engineering Manager** (lead): Task breakdown, dependencies, timeline
- **Technical Lead** (support): Technology decisions, architecture, feasibility
- **Full Stack Architect** (optional): System design, integration patterns

**Key Activities**:
- Read and understand PRD thoroughly
- Break requirements into specific tasks
- Identify dependencies and sequencing
- Define milestones and checkpoints
- Make technology stack decisions
- Estimate effort and timeline

**Outputs**:
- `TASKS.md` - Detailed task breakdown with dependencies
- `TECH_DECISIONS.md` - Technology choices and rationale
- `PLAN.md` - Implementation plan with milestones (optional)

**Success Criteria**:
- All PRD requirements covered by tasks
- Dependencies clearly mapped
- Tasks are independently testable
- Timeline is realistic
- Both agents signal `[[PROJECT_COMPLETE]]`

**Typical Duration**: 8-12 turns

---

### Phase 3: Implementation & Testing

**Goal**: Build working software according to plan

**Typical Roles**:
- **Lead Developer** (primary): Code implementation, feature development
- **Code Reviewer** (quality gate): Review code, find bugs, ensure quality
- **QA Engineer** (optional): Test execution, validation, bug reporting

**Key Activities**:
- Implement features per task list
- Write unit and integration tests
- Review code for quality and bugs
- Fix issues found during review
- Validate against PRD acceptance criteria
- Document usage and setup

**Outputs**:
- Working code (application files)
- Test files
- `README.md` - Setup and usage documentation
- `CODE_REVIEW.md` - Review findings (optional)

**Success Criteria**:
- All code functional and tested
- All tests passing
- Code Reviewer approves (no critical bugs)
- PRD acceptance criteria met
- Both/all agents signal `[[PROJECT_COMPLETE]]`

**Typical Duration**: 15-25 turns (including debugging)

---

## Instruction File Anatomy

Every instruction file **must** follow this structure:

```markdown
<!-- SECURITY_BOUNDARY_MARKER: DO NOT REMOVE -->
## CRITICAL: Project Directory Security
[... security template from ALL_MODELS_TEMPLATE.md ...]
<!-- SECURITY_BOUNDARY_MARKER: DO NOT REMOVE -->

═══════════════════════════════════════════════════════════
⚠️  CRITICAL REQUIREMENTS - READ FIRST ⚠️
═══════════════════════════════════════════════════════════

## 1. RESPONSE DELIMITER PROTOCOL (MANDATORY)
[... delimiter protocol from ALL_MODELS_TEMPLATE.md ...]

## 2. PROJECT COMPLETION SIGNAL
[... completion signal from ALL_MODELS_TEMPLATE.md ...]

═══════════════════════════════════════════════════════════

## Your Role: [ROLE_NAME] ([PHASE_NAME])

**Primary Responsibilities:**
- [Bullet list of core duties]

**Secondary Responsibilities:**
- [Bullet list of supporting activities]

**Team Position:**
- Reports to: [Who oversees this role]
- Collaborates with: [Other roles in this session]
- Decision Authority: [What this role can decide alone]

## Project Context

**Phase**: [Phase name]
**Working Directory:** [PROJECT_PATH]
**Input Artifacts:** [List of required input files]
**Output Artifacts:** [List of expected output files]
**Success Criteria:** [What defines completion]

## Workflow Phases

**Phase 1: [Activity Name]** (Turn 1-X)
- [ ] Step 1
- [ ] Step 2
- Exit criteria: [When to move to next phase]

[... more phases as needed ...]

## [Role-Specific Guidance Sections]

[Content varies by role - requirements writing, code patterns, etc.]

## Collaboration Protocols

**Communication Style:** [How to interact with teammates]
**With [Other Role]:** [Specific collaboration guidance]
**Decision Making:** [Authority levels and consensus needs]
**Reaching Team Consensus:** [How to finalize deliverables]

## Common Pitfalls to Avoid

**[Category]:**
- ⚠️ Don't [anti-pattern]
- ✅ Do [best practice]

## Definition of Done

This phase is complete when:
- [ ] [Specific completion criterion]
- [ ] [Another completion criterion]

**You may signal [[PROJECT_COMPLETE]] when:**
[Clear conditions for completion]
```

---

## Creating New Instruction Files

### Step 1: Determine Project Scope and Phases

**Questions to Ask**:
1. What is the end deliverable? (CLI tool, web app, library, etc.)
2. How complex is the domain? (financial calculations, game logic, data processing)
3. Can we use the standard 3-phase workflow? Or do we need more/fewer phases?
4. What specialized knowledge is needed? (finance, game design, security, etc.)

**Decision Matrix**:

| Project Type | Recommended Phases | Notes |
|--------------|-------------------|-------|
| Simple CLI tool | 2 phases (Planning + Implementation) | Skip PRD for very simple tools |
| Standard application | 3 phases (PRD + Planning + Implementation) | Default workflow |
| Complex system | 4+ phases (PRD + Architecture + Implementation + Testing) | Add phases for complexity |
| Enhancement to existing code | 2 phases (Planning + Implementation) | Requirements often clear |
| Web UI for existing app | 3 phases (Web PRD + Web Planning + Web Implementation) | Specialized variant |

### Step 2: Choose Roles for Each Phase

**Phase 1 (Requirements) - Pick 2:**
- **Product Manager** (generalist, user-focused) - *Default lead*
- **Business Analyst** (technical requirements, validation rules)
- **UX Designer** (user experience, interface design)
- **Security Analyst** (security requirements, threat modeling)
- **Domain Expert** (finance, healthcare, gaming, etc.)

**One role must be designated as lead** (final authority on deliverable)

**Phase 2 (Planning) - Pick 2:**
- **Engineering Manager** (task breakdown, timeline) - *Default lead*
- **Technical Lead** (architecture, tech stack decisions)
- **Full Stack Architect** (system design, integration patterns)
- **Security Architect** (security design, threat mitigation)

**One role must be designated as lead** (final authority on task list)

**Phase 3 (Implementation) - Pick 2-3:**
- **Lead Developer** (primary implementation) - *Default lead*
- **Code Reviewer** (quality gate, bug finding) - *Highly recommended*
- **QA Engineer** (testing, validation)
- **Security Reviewer** (security validation, vulnerability scanning)
- **Performance Engineer** (optimization, benchmarking)

**One role must be designated as lead** (final authority on code)

**Role Assignment Guidelines**:
- **Minimum**: 2 roles per phase (for collaboration and quality)
- **Recommended**: 2 roles per phase (sweet spot)
- **Maximum**: 4 roles per phase (avoid too many cooks)
- **Authority**: Always designate one role as final authority

### Step 3: Define Role Responsibilities

For each role, document:

**Primary Responsibilities** (3-6 items):
- Core activities this role owns
- Deliverables they're responsible for
- Decisions they have final say on

**Secondary Responsibilities** (2-4 items):
- Supporting activities
- Areas where they provide input but don't own

**Decision Authority Levels**:
1. **Autonomous**: Can decide without consulting others
   - Example: Product Manager decides PRD structure
2. **Collaborative**: Requires consensus with other roles
   - Example: Both PMs must agree to request clarification
3. **Escalation**: Requires human/stakeholder input
   - Example: Fundamental scope changes

**Template**:
```markdown
## Your Role: [Role Name] ([Phase Name])

**Primary Responsibilities:**
- [What they own and are accountable for]
- [Key deliverables they produce]
- [Decisions they make autonomously]

**Secondary Responsibilities:**
- [Supporting activities]
- [Areas where they provide input]

**Team Position:**
- Reports to: [Stakeholder or manager]
- Collaborates with: [Other role names in this session]
- Decision Authority: [What they can decide alone, what needs consensus]
```

### Step 4: Map Input/Output Artifacts

**For Each Phase**, define:

**Required Inputs**:
- What files/documents does this phase need to start?
- Are any inputs optional?
- What happens if inputs are incomplete?

**Expected Outputs**:
- What files/documents must this phase produce?
- What's the primary deliverable vs. supporting docs?
- What format should outputs use?

**Example - Phase 1 (Requirements)**:
```markdown
**Input Artifacts:**
- USER_REQUEST.md - Initial stakeholder description (required)
- USER_RESPONSE.md - Answers to clarification questions (optional, for iterations)

**Output Artifacts:**
- PRD.md - Product Requirements Document (primary deliverable)
- OR CLARIFICATION_REQUEST.md - Questions for stakeholder (if info insufficient)
```

**Example - Phase 2 (Planning)**:
```markdown
**Input Artifacts:**
- PRD.md - From Phase 1 (required)

**Output Artifacts:**
- TASKS.md - Task breakdown with dependencies (primary)
- TECH_DECISIONS.md - Technology choices (primary)
- PLAN.md - Implementation plan with milestones (optional)
```

**Example - Phase 3 (Implementation)**:
```markdown
**Input Artifacts:**
- PRD.md - From Phase 1 (required)
- TASKS.md - From Phase 2 (required)
- TECH_DECISIONS.md - From Phase 2 (required)

**Output Artifacts:**
- [source code files] - Working implementation (primary)
- [test files] - Automated tests (primary)
- README.md - Setup and usage docs (required)
- CODE_REVIEW.md - Review findings (optional)
```

### Step 5: Define Workflow Phases Within Session

Break the session's work into **3-5 mini-phases** with clear progression:

**Phase Template**:
```markdown
**Phase [N]: [Activity Name]** (Turn X-Y)
- [ ] Action item 1
- [ ] Action item 2
- [ ] Action item 3
- Exit criteria: [What must be true to move to next phase]
```

**Example - Requirements Session**:
```markdown
**Phase 1: Initial Analysis** (Turn 1-2)
- [ ] Read USER_REQUEST.md thoroughly
- [ ] Understand core problem
- [ ] Identify clear vs. unclear information
- [ ] List initial questions
- Exit criteria: Complete understanding of what was provided

**Phase 2: Collaborative Analysis** (Turn 3-5)
- [ ] Discuss with Business Analyst
- [ ] Share user-focused concerns
- [ ] Identify gaps blocking PRD
- [ ] Reach consensus: proceed or clarify?
- Exit criteria: Team agreement on path forward

**Phase 3: PRD Creation** (Turn 6-8)
- [ ] Write comprehensive PRD.md
- [ ] Document assumptions
- [ ] Define acceptance criteria
- [ ] Get Business Analyst approval
- [ ] Signal [[PROJECT_COMPLETE]]
- Exit criteria: PRD complete and approved
```

**Guidelines**:
- Each mini-phase should be 2-5 turns
- Each should have clear entry and exit criteria
- Progress should be logical and sequential
- Include checkboxes for clarity

### Step 6: Add Domain-Specific Guidance

This is where you tailor the instruction file to your **specific project type**.

**Categories of Guidance**:

1. **Technical Patterns**
   - Code structure examples
   - Algorithm guidance
   - Library recommendations

2. **Domain Knowledge**
   - Financial calculations: Use Decimal, not float
   - Game development: Frame rates, collision detection
   - Security: Input validation, authentication patterns

3. **Quality Standards**
   - Testing requirements
   - Code review criteria
   - Documentation standards

4. **Common Pitfalls**
   - Anti-patterns to avoid
   - Frequent mistakes in this domain
   - Edge cases often missed

**Example - Financial Calculations**:
```markdown
## Financial Calculation Guidance

### Precision Requirements

**CRITICAL: Use Decimal, Not Float**
```python
from decimal import Decimal

# ✅ CORRECT
principal = Decimal("10000.00")
apr = Decimal("0.185")
interest = principal * apr

# ❌ WRONG - Float introduces rounding errors
principal = 10000.00
apr = 0.185
interest = principal * apr  # May be 1850.0000000001
```

### Interest Calculation Formulas

**Simple Interest**:
```
I = P × r × t
```

**Compound Interest (Monthly)**:
```
A = P × (1 + r/12)^n
I = A - P
```

Where:
- P = Principal (Decimal)
- r = Annual rate (Decimal, e.g., 0.185 for 18.5%)
- t = Time in years (Decimal)
- n = Number of months (int)

### Common Pitfalls

- ⚠️ Don't use float for currency
- ⚠️ Don't forget to round to 2 decimal places for display
- ⚠️ Don't assume 30-day months (use actual days)
- ✅ Do validate all inputs are positive
- ✅ Do test with edge cases (0%, very large numbers)
```

**Example - Game Development**:
```markdown
## Game Development Guidance

### Frame Rate and Timing

**Delta Time Pattern**:
```python
def update(self, dt):
    """
    dt: Time elapsed since last frame (seconds)
    """
    # ✅ CORRECT - Frame-rate independent
    self.position += self.velocity * dt

    # ❌ WRONG - Tied to frame rate
    self.position += self.velocity
```

### Collision Detection

**Bounding Box Method**:
```python
def check_collision(obj1, obj2):
    return (obj1.x < obj2.x + obj2.width and
            obj1.x + obj1.width > obj2.x and
            obj1.y < obj2.y + obj2.height and
            obj1.y + obj1.height > obj2.y)
```

### Common Pitfalls

- ⚠️ Don't update physics in rendering code
- ⚠️ Don't hardcode positions/speeds (use config)
- ⚠️ Don't forget to handle window resize
- ✅ Do separate game logic from rendering
- ✅ Do test with different frame rates
```

### Step 7: Define Collaboration Protocols

Specify **how roles work together** in this session.

**Template**:
```markdown
## Collaboration Protocols

**Communication Style:**
[How to communicate with teammates - tone, focus areas, etc.]

**With [Other Role Name]:**
- They focus on: [What they own]
- You focus on: [What you own]
- Combined perspective: [How you complement each other]
- Defer to them on: [When to follow their lead]
- Lead the decision on: [When you have final say]

**Decision Making:**
- You can decide autonomously:
  - [List of decisions you own]

- Requires [Other Role] consensus:
  - [List of joint decisions]

- Requires stakeholder input (escalation):
  - [List of decisions needing human input]

**Reaching Team Consensus:**
Before signaling [[PROJECT_COMPLETE]]:
1. [Specific consensus requirement]
2. [Another requirement]
3. [Final requirement]
```

**Example - Product Manager + Business Analyst**:
```markdown
## Collaboration Protocols

**Communication Style:**
- Think from user's perspective
- Focus on "what" and "why", not "how"
- Be clear about priorities and trade-offs
- Acknowledge Business Analyst's technical insights

**With Business Analyst:**
- They focus on: Calculation logic and technical details
- You focus on: User needs and experience
- Combined perspective: Comprehensive requirements
- Defer to them on: Technical calculation questions
- Lead the decision on: Whether to request clarifications

**Decision Making:**
- You can decide autonomously:
  - PRD structure and format
  - Priority of requirements
  - User-facing feature descriptions
  - Scope boundaries (MVP vs. future)

- Requires Business Analyst consensus:
  - Whether to proceed with PRD or request clarification
  - Assumptions to make when info is incomplete
  - Technical requirement specifications

- Requires stakeholder input (escalation):
  - Fundamental problem interpretation
  - Critical edge case handling
  - Feature priority when unclear

**Reaching Team Consensus:**
Before signaling [[PROJECT_COMPLETE]]:
1. Both you AND Business Analyst must agree PRD is complete
2. All critical requirements must be documented
3. All assumptions must be clearly stated
4. Acceptance criteria must be testable
```

### Step 8: Add Examples and Anti-Patterns

Help the AI learn by showing **good vs. bad** examples.

**Categories**:
1. Good/bad requirements
2. Good/bad task breakdowns
3. Good/bad code patterns
4. Good/bad documentation

**Template**:
```markdown
## Common Pitfalls to Avoid

**[Category Name]:**
- ⚠️ Don't [anti-pattern with brief explanation]
- ⚠️ Don't [another anti-pattern]
- ✅ Do [best practice]
- ✅ Do [another best practice]

**Example (Good)**:
```
[Show good example]
```

**Example (Bad)**:
```
[Show bad example and why it's bad]
```
```

**Example - Requirements Writing**:
```markdown
## Common Pitfalls to Avoid

**Ambiguity:**
- ⚠️ Don't use vague terms like "user-friendly", "fast", "accurate" without definition
- ⚠️ Don't leave edge cases unaddressed
- ⚠️ Don't hide assumptions
- ✅ Do be specific and quantify when possible

**Good Requirements (Specific, Testable):**
- ✅ FR-1: System shall calculate total interest with precision to 2 decimal places
- ✅ FR-2: System shall display recommendation indicating which option costs less and by how much
- ✅ FR-3: System shall validate monthly payment is greater than zero and less than total debt

**Bad Requirements (Vague, Untestable):**
- ❌ "Calculator should be accurate"
- ❌ "Output should be user-friendly"
- ❌ "System should handle edge cases"
```

### Step 9: Define Completion Criteria

Be **crystal clear** about when the phase is done.

**Template**:
```markdown
## Definition of Done

This [phase name] phase is complete when:
- [ ] [Specific, measurable criterion]
- [ ] [Another criterion]
- [ ] [Final criterion]

**You may signal [[PROJECT_COMPLETE]] when:**
1. [Condition 1]
2. [Condition 2]
3. [Condition 3]

**Examples of READY:**
- [Concrete example of complete work]
- [Another example]

**Examples of NOT READY:**
- [Example of incomplete work]
- [What's missing in this case]
```

**Example**:
```markdown
## Definition of Done

This requirements phase is complete when:
- [ ] PRD.md exists and is comprehensive
- [ ] All critical requirements are documented
- [ ] Edge cases are identified and addressed
- [ ] Acceptance criteria are clear and testable
- [ ] Assumptions are explicitly documented
- [ ] Business Analyst has reviewed and approved
- [ ] Both team members agree it's ready for planning team

**You may signal [[PROJECT_COMPLETE]] when:**
1. PRD.md is written and complete
2. Business Analyst confirms they agree
3. All must-have information is captured
4. You're confident planning team can work from this PRD

**Examples of READY:**
- All user requirements clearly specified
- Edge cases documented with expected behavior
- Acceptance criteria are testable
- Reasonable assumptions documented where needed

**Examples of NOT READY:**
- Critical calculation method is ambiguous
- Edge cases have no defined handling
- Requirements contradict each other
- Missing fundamental information about inputs/outputs
```

### Step 10: Prepend Mandatory Template

**CRITICAL**: Every instruction file must start with the security and protocol template.

**Process**:
1. Copy `templates/ALL_MODELS_TEMPLATE.md` to your instruction file
2. Replace `[PROJECT_PATH]` with the actual project path variable
3. Customize the completion signal section for your phase
4. Add your role-specific content after the template

**File Structure**:
```markdown
<!-- Content from ALL_MODELS_TEMPLATE.md -->
<!-- Security boundaries -->
<!-- Response delimiter protocol -->
<!-- Project completion signal -->

<!-- Your role-specific content starts here -->
## Your Role: [ROLE_NAME]
...
```

**Important**: Do NOT modify the security boundary markers or response delimiter format. These are critical for Orchestrator's parsing and filtering.

---

## Role Definition Guidelines

### Naming Conventions

**Format**: `ROLE_[RoleName]_[PhaseName].md`

**Examples**:
- `ROLE_ProductManager_Requirements.md`
- `ROLE_EngineeringManager_Planning.md`
- `ROLE_LeadDeveloper_Implementation.md`
- `ROLE_FullStackDeveloper_WebUI.md`

**Why This Format**:
- Clear indication this is a role file
- Role name identifies the persona
- Phase name identifies which session this belongs to
- Easy to organize and find

### Role Characteristics

A good role definition should be:

**1. Specific**
- ❌ "Developer" (too vague)
- ✅ "Lead Developer" (implementation focus)
- ✅ "Full Stack Developer" (backend + frontend)

**2. Focused**
- Each role should have 3-6 primary responsibilities
- Don't try to make one role do everything
- Clear boundaries with other roles

**3. Actionable**
- Role should know exactly what to do each turn
- Workflow phases guide progression
- Clear decision-making authority

**4. Collaborative**
- Defines how to work with other roles
- Specifies when to defer to others
- Requires consensus on key decisions

### Authority Levels

Every role needs clear **decision-making authority**:

**Level 1: Autonomous Decisions**
- Can decide without consulting others
- Example: Product Manager decides PRD structure
- Example: Lead Developer chooses variable names

**Level 2: Collaborative Decisions**
- Requires consensus with one or more other roles
- Example: Product Manager + Business Analyst agree to request clarification
- Example: Lead Developer + Code Reviewer agree code is ready

**Level 3: Escalation Decisions**
- Requires human stakeholder input
- Example: Major scope changes
- Example: Technology stack changes after planning phase

**Level 4: Final Authority** (one role per phase)
- This role has the final say on the deliverable
- Can break ties if consensus can't be reached
- Signals project completion first

**Template**:
```markdown
**Decision Authority:**

**Autonomous (you decide alone):**
- [Decision type 1]
- [Decision type 2]

**Collaborative (requires consensus with [Other Role]):**
- [Joint decision 1]
- [Joint decision 2]

**Escalation (requires human/stakeholder input):**
- [Escalation scenario 1]
- [Escalation scenario 2]

**Final Authority:** [Yes/No - if yes, you have tiebreaker power]
```

---

## Authority Hierarchy

### The Lead Role Pattern

**Every phase must have exactly one lead role** with final authority.

**Responsibilities of Lead Role**:
1. **Primary deliverable ownership**: They write/create the main output
2. **Timeline management**: They drive the session forward
3. **Consensus building**: They ensure team agreement
4. **Tiebreaking**: If roles can't agree, lead makes final call
5. **Quality gate**: They decide when work is "done"

**How to Designate**:
```markdown
**Team Position:**
- Reports to: [Stakeholder]
- Collaborates with: [Other roles]
- Decision Authority: **LEAD ROLE** - Final authority on [deliverable name]
```

**Default Lead Roles**:
- Phase 1 (Requirements): **Product Manager**
- Phase 2 (Planning): **Engineering Manager**
- Phase 3 (Implementation): **Lead Developer**

### Supporting Role Pattern

All non-lead roles are supporting roles.

**Responsibilities of Supporting Roles**:
1. **Provide expertise**: Contribute specialized knowledge
2. **Review and validate**: Check lead's work
3. **Collaborate**: Work with lead to improve quality
4. **Consensus**: Agree before signaling completion

**How to Designate**:
```markdown
**Team Position:**
- Reports to: [Stakeholder]
- Collaborates with: [Lead role name]
- Decision Authority: Expert input on [domain], must approve deliverable
```

### Escalation Patterns

Some decisions are **too big for AI** and need human input.

**When to Escalate**:
- Fundamental scope changes
- Major architectural pivots
- Budget/timeline concerns
- Legal/compliance issues
- Conflicting requirements from different stakeholders

**How to Escalate**:
```markdown
**If Critical Issue Arises**:
1. Document the issue clearly
2. Explain why it blocks progress
3. Provide 2-3 options with pros/cons
4. Create ESCALATION_REQUEST.md
5. Wait for human decision before proceeding
```

---

## Best Practices

### 1. Start with Existing Examples

**Don't start from scratch**. Copy an existing instruction file that's close to what you need:

- Terminal app? Copy `ROLE_ProductManager_Requirements.md`
- Web UI? Copy `ROLE_FullStackDeveloper_WebUI.md`
- Planning? Copy `ROLE_EngineeringManager_Planning.md`

**Then customize**:
- Change role name and responsibilities
- Update domain-specific guidance
- Adjust workflow phases
- Modify collaboration protocols

### 2. Be Specific, Not Generic

**Bad** (too generic):
```markdown
**Primary Responsibilities:**
- Create good requirements
- Work with team
- Make documents
```

**Good** (specific and actionable):
```markdown
**Primary Responsibilities:**
- Analyze stakeholder input and extract core requirements
- Define clear, testable acceptance criteria
- Identify edge cases and error scenarios
- Ask clarifying questions when requirements are ambiguous
- Write comprehensive Product Requirements Document (PRD)
```

### 3. Provide Examples Generously

AIs learn best from examples. Include:
- Example requirements (good and bad)
- Example code patterns
- Example task breakdowns
- Example collaboration exchanges

**Format**:
```markdown
**Good Example:**
```
[Show correct approach]
```

**Why this works:** [Explain the reasoning]

**Bad Example:**
```
[Show incorrect approach]
```

**Why this fails:** [Explain the problem]
```

### 4. Use Checklists for Workflow

Checklists help AIs track progress:

```markdown
**Phase 1: Analysis** (Turn 1-2)
- [ ] Read USER_REQUEST.md
- [ ] Identify clear vs. unclear requirements
- [ ] List initial questions
- Exit criteria: Complete understanding of input
```

Benefits:
- Clear progression through phases
- Easy to see what's done vs. remaining
- Exit criteria prevent premature advancement

### 5. Emphasize Communication Protocols

**Critical sections**:
- Response delimiters (MUST use)
- Collaboration style (how to interact)
- Decision authority (who decides what)
- Consensus requirements (when to agree)

**Repeat important protocols**:
- Mention response delimiters in multiple places
- Remind about `[[PROJECT_COMPLETE]]` signal
- Emphasize collaboration over solo work

### 6. Include Domain Expertise

If your project requires specialized knowledge, **teach it in the instruction file**:

**Financial domain**:
- Interest calculation formulas
- Decimal precision requirements
- Industry standards (APR vs. APY)

**Game development domain**:
- Frame-rate independence
- Collision detection patterns
- State management

**Security domain**:
- Input validation requirements
- Authentication/authorization patterns
- Common vulnerabilities (OWASP)

**Web development domain**:
- CORS configuration
- REST API design
- Responsive design patterns

### 7. Test with Simple Projects First

Before using new instruction files on complex projects:

1. **Test with simple example**: Use a straightforward project
2. **Review outputs**: Check if agents followed instructions
3. **Iterate on clarity**: Fix confusing sections
4. **Add missing guidance**: Where did agents struggle?
5. **Refine collaboration**: Did roles work well together?

### 8. Version Your Instruction Files

As you improve instruction files:

```markdown
# [Role Name] - [Phase Name]

**Version**: 1.2
**Last Updated**: 2025-11-13
**Changes**:
- v1.2: Added section on error handling patterns
- v1.1: Clarified collaboration protocol with Code Reviewer
- v1.0: Initial version
```

### 9. Document Lessons Learned

After each project, capture:
- What worked well
- What was confusing
- What gaps existed
- How roles collaborated

Use this to improve instruction files over time.

### 10. Keep Templates Organized

**Recommended structure**:
```
templates/
├── ALL_MODELS_TEMPLATE.md          # Mandatory prefix
├── projects/
│   ├── cli-apps/
│   │   ├── ROLE_ProductManager_Requirements.md
│   │   ├── ROLE_EngineeringManager_Planning.md
│   │   └── ROLE_LeadDeveloper_Implementation.md
│   ├── web-apps/
│   │   ├── ROLE_FullStackDeveloper_WebUI.md
│   │   └── ROLE_CodeReviewer_WebUI.md
│   └── games/
│       ├── ROLE_GameDesigner_Requirements.md
│       └── ROLE_GameDeveloper_Implementation.md
└── README.md                        # Template catalog
```

---

## Common Patterns

### Pattern 1: Iterative Clarification (Requirements Phase)

**Use When**: Requirements might be incomplete

**Structure**:
```markdown
## Handling Incomplete Information

### Decision Framework: Can We Write the PRD?

**Produce PRD.md if:**
- ✅ Core problem is clearly defined
- ✅ Primary use case is understood
- ✅ Can make reasonable assumptions for minor details

**Request Clarification if:**
- ❌ Multiple valid interpretations exist
- ❌ Critical edge cases have no clear handling
- ❌ Assumptions would likely require major rework

### Clarification Request Process:
1. Work with [Other Role] to compile questions
2. Categorize by criticality (blocking vs. nice-to-have)
3. Provide context for why each question matters
4. Create CLARIFICATION_REQUEST.md
5. Explain what you'll do once you receive answers
```

### Pattern 2: Dependency Mapping (Planning Phase)

**Use When**: Tasks have complex dependencies

**Structure**:
```markdown
## Dependency Management

### Identifying Dependencies

**Technical Dependencies:**
- Task B needs function/data from Task A

**Logical Dependencies:**
- Core logic before UI (can't display what doesn't exist)

**Anti-Dependencies (Can Be Parallel):**
- Documentation can happen alongside implementation

### Dependency Notation

```
## Task Dependencies

graph TD
    T1[Core Calculations] --> T2[Scenario A]
    T1 --> T3[Scenario B]
    T2 --> T5[Comparison]
    T3 --> T5
```

**Critical Path**: T1 → T2 → T5 (longest sequence)
**Parallel Opportunities**: T4 can happen alongside T1-T3
```

### Pattern 3: Review Gate (Implementation Phase)

**Use When**: Code quality is critical

**Structure**:
```markdown
## Code Review Process

**Developer Responsibilities:**
1. Implement feature per task specification
2. Write tests for new code
3. Self-review before requesting review
4. Submit for Code Reviewer evaluation

**Code Reviewer Responsibilities:**
1. Review for correctness, not style preferences
2. Test functionality thoroughly
3. Identify bugs and edge cases
4. Approve or request changes

**Review Criteria:**
- [ ] Code matches PRD requirements
- [ ] All edge cases handled
- [ ] Tests exist and pass
- [ ] No security vulnerabilities
- [ ] Performance is acceptable

**Approval Process:**
- ❌ Critical bugs: MUST fix before approval
- ⚠️ Medium issues: Should fix, negotiable
- 💡 Suggestions: Optional improvements

**Both must agree code is ready before signaling [[PROJECT_COMPLETE]]**
```

### Pattern 4: Parallel Workstreams (Web UI Pattern)

**Use When**: Backend and frontend can develop simultaneously

**Structure**:
```markdown
## Parallel Development Strategy

### Workstream 1: Backend (Lead Developer)
**Phase 1**: API endpoint creation
**Phase 2**: Integration with existing code
**Phase 3**: Testing and documentation

### Workstream 2: Frontend (can be parallel)
**Phase 1**: Component development with mock data
**Phase 2**: API client implementation
**Phase 3**: Integration with real backend

### Integration Point (requires both workstreams)
**Phase 4**: Connect frontend to backend
**Phase 5**: End-to-end testing

### Coordination:
- Backend defines API contract first
- Frontend uses contract to build against mock data
- Both streams converge at integration point
```

---

## Examples and Templates

### Example 1: Custom Role for Financial Domain

**Scenario**: You need a specialized "Financial Analyst" role for a budgeting app.

**File**: `ROLE_FinancialAnalyst_Requirements.md`

**Key Customizations**:
1. **Domain expertise** in personal finance
2. **Validation rules** for budgeting calculations
3. **Regulatory compliance** awareness (privacy, etc.)
4. **Common user patterns** in budgeting apps

**Excerpt**:
```markdown
## Your Role: Financial Analyst (Requirements Phase)

**Primary Responsibilities:**
- Analyze user's budgeting needs from financial perspective
- Define clear calculation rules for income, expenses, savings
- Ensure compliance with financial best practices
- Identify edge cases in budgeting scenarios (variable income, debt, etc.)
- Specify data validation rules for financial inputs

## Financial Domain Guidance

### Budget Calculation Principles

**Income Categories:**
- Gross income (before taxes)
- Net income (after taxes)
- Variable income (commissions, bonuses)
- Passive income (investments, rental)

**Expense Categories:**
- Fixed expenses (rent, loan payments)
- Variable expenses (groceries, entertainment)
- Periodic expenses (annual insurance, quarterly taxes)
- Discretionary vs. necessary

**Savings Rules:**
- Emergency fund target: 3-6 months expenses
- Debt payment priority: Highest interest first
- Savings rate: Percentage of net income

### Validation Rules

**Income Validation:**
- ✅ Must be positive decimal
- ✅ Support monthly, bi-weekly, annual entry
- ✅ Convert all to common period (monthly) for calculations

**Expense Validation:**
- ✅ Must be positive or zero
- ✅ Total expenses should not exceed income (warn user if they do)
- ✅ Support recurring vs. one-time expenses

### Common Edge Cases

**Variable Income:**
- How to budget when income fluctuates?
- Recommendation: Use average of last 3-6 months

**Irregular Expenses:**
- Annual insurance: Divide by 12 for monthly budget
- Quarterly taxes: Reserve monthly amount

**Debt Payoff:**
- Minimum payment vs. accelerated payoff
- Interest calculation during payoff period
```

### Example 2: Custom Role for Game Development

**Scenario**: You need a "Game Designer" role for a platformer game.

**File**: `ROLE_GameDesigner_Requirements.md`

**Key Customizations**:
1. **Game design principles** (difficulty curve, feedback loops)
2. **Player experience** focus
3. **Game mechanics** specification
4. **Balance and tuning** considerations

**Excerpt**:
```markdown
## Your Role: Game Designer (Requirements Phase)

**Primary Responsibilities:**
- Define core gameplay mechanics
- Specify player controls and feel
- Design level progression and difficulty curve
- Identify win/lose conditions
- Define game balance parameters (speed, jump height, enemy AI)

## Game Design Guidance

### Core Mechanics Specification

**Player Movement:**
- Walk speed: [X] pixels/second
- Run speed: [Y] pixels/second
- Jump height: [Z] pixels
- Double jump: Yes/No
- Wall jump: Yes/No

**Player Actions:**
- Attack: [damage, range, cooldown]
- Defend: [block %, duration]
- Special abilities: [list and specify]

### Difficulty Curve

**Level 1 (Tutorial):**
- Introduce one mechanic at a time
- No fail states
- Gentle learning curve

**Level 2-5 (Easy):**
- Combine 2-3 mechanics
- Introduce first challenges
- Forgiving timing windows

**Level 6-10 (Medium):**
- All mechanics available
- Tighter timing requirements
- Introduce enemy variety

### Player Feedback

**Visual Feedback:**
- Player takes damage: Flash red, brief invulnerability
- Player collects item: Particle effect, sound
- Player achieves goal: Victory animation, score display

**Audio Feedback:**
- Jump: Light "boing" sound
- Land: Thud proportional to fall distance
- Damage: Pain sound + music ducks
- Victory: Triumphant jingle

### Balance Parameters

**Too Easy Indicators:**
- Player never takes damage
- Levels completed in < 30 seconds
- No challenge or engagement

**Too Hard Indicators:**
- Player dies repeatedly in same spot
- Frustration exceeds fun
- Requires pixel-perfect execution

**Target:**
- 60-70% success rate on first attempt (medium difficulty)
- Learning curve: Improvement with practice
- Fair failures: Player knows why they failed
```

### Example 3: Custom Session for Code Migration

**Scenario**: You're migrating legacy code to a new framework, don't need full PRD.

**File**: `ROLE_MigrationArchitect_Planning.md`

**Key Customizations**:
1. **Two-phase workflow** (Planning + Implementation, skip PRD)
2. **Migration-specific concerns** (compatibility, testing, rollback)
3. **Risk assessment** for migration
4. **Parallel operation** strategy (old and new systems)

**Excerpt**:
```markdown
## Your Role: Migration Architect (Planning Phase)

**Primary Responsibilities:**
- Analyze existing legacy code structure
- Plan migration path to new framework
- Identify compatibility issues and solutions
- Define testing strategy to verify migration correctness
- Create rollback plan in case of critical issues

## Migration Planning Guidance

### Analysis Phase

**Legacy System Assessment:**
- [ ] Identify all dependencies
- [ ] Map existing features and functionality
- [ ] Note deprecated patterns or libraries
- [ ] Document current test coverage

**New Framework Requirements:**
- [ ] Study new framework patterns
- [ ] Identify equivalent approaches for legacy patterns
- [ ] Note new capabilities to leverage
- [ ] Plan for framework-specific optimizations

### Migration Strategy

**Approach Options:**

**Big Bang Migration:**
- Pros: Clean cut, one-time effort
- Cons: High risk, potential for major breakage
- When to use: Small codebase, comprehensive tests

**Incremental Migration:**
- Pros: Lower risk, gradual rollout
- Cons: Longer timeline, dual maintenance
- When to use: Large codebase, production system

**Strangler Pattern:**
- Pros: Both systems run in parallel, gradual replacement
- Cons: Complex routing, longer transition
- When to use: Critical production system, zero downtime required

### Risk Assessment

**High Risk Areas:**
- [ ] Database schema changes
- [ ] Authentication/authorization systems
- [ ] Payment processing
- [ ] Data migration (user data, historical records)

**Mitigation Strategies:**
- Comprehensive testing at each step
- Feature flags to enable/disable new code
- Database migration with rollback scripts
- Parallel operation period for validation

### Testing Strategy

**Migration Validation:**
- [ ] Unit tests pass (100% of existing tests)
- [ ] Integration tests pass
- [ ] Feature parity verified (new = old behavior)
- [ ] Performance benchmarks (new ≥ old performance)
- [ ] User acceptance testing

**Rollback Criteria:**
- Critical bug in production
- Performance degradation > 20%
- Data corruption detected
- User-reported blocking issues
```

---

## Troubleshooting

### Issue: Agents Aren't Using Response Delimiters

**Symptoms**:
- Communication between agents is broken
- Orchestrator can't parse responses
- Agents seem to be talking past each other

**Diagnosis**:
Check if the mandatory template is present at the top of instruction file:
```markdown
## 1. RESPONSE DELIMITER PROTOCOL (MANDATORY)
```

**Solutions**:
1. Ensure `ALL_MODELS_TEMPLATE.md` is prepended to every instruction file
2. Add reminder in multiple places:
   ```markdown
   **REMEMBER**: Wrap your response in delimiters:
   <<<RESPONSE_START>>>
   Your message here
   <<<RESPONSE_END>>>
   ```
3. Include example of proper delimiter usage

### Issue: Agents Signal Completion Too Early

**Symptoms**:
- Deliverables are incomplete
- Quality is poor
- Other agents haven't reviewed

**Diagnosis**:
"Definition of Done" section is too vague or missing.

**Solutions**:
1. Make completion criteria very specific:
   ```markdown
   ## Definition of Done

   **You may signal [[PROJECT_COMPLETE]] ONLY when:**
   1. PRD.md file exists with ALL required sections
   2. Business Analyst has explicitly approved
   3. All edge cases are documented
   4. No open questions remain
   ```

2. Add negative examples:
   ```markdown
   **Examples of NOT READY:**
   - Missing sections in PRD
   - Business Analyst hasn't reviewed yet
   - Edge cases are marked "TBD"
   ```

3. Require explicit approval from other roles:
   ```markdown
   **Consensus Requirement:**
   Both Product Manager AND Business Analyst must agree before
   EITHER can signal [[PROJECT_COMPLETE]].
   ```

### Issue: Agents Signal Completion Too Late

**Symptoms**:
- Session runs for too many turns (>20 for planning, >30 for implementation)
- Agents keep refining when work is already good
- Diminishing returns on quality improvements

**Diagnosis**:
Completion criteria are too strict or perfectionist.

**Solutions**:
1. Add "good enough" guidance:
   ```markdown
   **Remember**: Perfect is the enemy of done.
   - All critical requirements met? ✅ Ready
   - Minor improvements possible? ⚠️ Don't block on this
   - Nice-to-have features? 💡 Save for v2
   ```

2. Set turn limits:
   ```markdown
   **Timeline**:
   - Target completion: 8-10 turns
   - If you reach turn 12 and core deliverable is solid, signal completion
   ```

3. Provide calibration examples:
   ```markdown
   **This PRD is READY (example):**
   - All requirements specified
   - 2 minor assumptions documented
   - 1 edge case marked "low priority to address in implementation"

   **This PRD is OVER-SPECIFIED (too much):**
   - Requirements include implementation details
   - Every possible edge case addressed
   - Multiple alternatives for each requirement
   ```

### Issue: Roles Don't Collaborate Well

**Symptoms**:
- Agents work in isolation
- No discussion or feedback between roles
- Deliverable created without consensus

**Diagnosis**:
Collaboration protocols are unclear or missing.

**Solutions**:
1. Make collaboration explicit in workflow:
   ```markdown
   **Phase 2: Collaborative Analysis** (Turn 3-5)
   - [ ] Share your initial thoughts with [Other Role]
   - [ ] Listen to their perspective
   - [ ] Discuss areas of disagreement
   - [ ] Find common ground
   - Exit criteria: Both roles agree on approach
   ```

2. Define communication style:
   ```markdown
   **Communication Pattern:**
   - Turn 1: You analyze independently
   - Turn 2: Other Role analyzes independently
   - Turn 3: You share findings, ask for their input
   - Turn 4: Other Role responds, provides feedback
   - Turn 5: You incorporate feedback, reach consensus
   ```

3. Require explicit approval:
   ```markdown
   **Before Creating PRD.md:**
   1. Draft outline of PRD structure
   2. Share with Business Analyst for feedback
   3. Incorporate their technical input
   4. THEN write full PRD
   5. Request their formal review
   6. Address any concerns
   7. Get explicit approval: "Business Analyst, do you approve this PRD?"
   ```

### Issue: Wrong AI Model for Role

**Symptoms**:
- Role requirements don't match model capabilities
- Poor quality outputs
- Model struggles with domain-specific tasks

**Diagnosis**:
Model assignment doesn't match role needs.

**Solutions**:
1. Match models to strengths:
   - **Claude Code**: Implementation, code review, technical architecture
   - **Gemini**: Analysis, review, planning, requirements
   - **Qwen**: Flexible, can handle most roles

2. Provide model-specific guidance:
   ```markdown
   ## For Claude Code Users
   [Claude-specific tips and patterns]

   ## For Gemini Users
   [Gemini-specific tips and patterns]
   ```

3. Adjust role complexity to model capability

### Issue: Domain Expertise Is Insufficient

**Symptoms**:
- Agents make domain-specific errors
- Missing industry best practices
- Incorrect calculations or logic

**Diagnosis**:
Instruction file doesn't teach enough domain knowledge.

**Solutions**:
1. Add comprehensive domain guidance section (see Examples above)
2. Include formulas, calculations, standards
3. Provide code examples and patterns
4. Link to external resources (with WebFetch):
   ```markdown
   **Reference Documentation:**
   - Financial regulations: [URL]
   - Industry standards: [URL]
   - Best practices guide: [URL]
   ```

### Issue: Outputs Don't Match Expected Format

**Symptoms**:
- Files created with wrong names
- Missing required sections
- Format doesn't match examples

**Diagnosis**:
Output specifications are vague.

**Solutions**:
1. Provide exact template:
   ```markdown
   ## PRD.md Structure (FOLLOW THIS EXACTLY)

   ```markdown
   # Product Requirements Document: [Project Name]

   ## 1. Problem Statement
   [Content here]

   ## 2. Objectives
   [Content here]
   ```
   ```

2. Show complete example output from a real project

3. Add output validation checklist:
   ```markdown
   **Before Finalizing PRD.md:**
   - [ ] File named exactly "PRD.md"
   - [ ] Contains all 13 sections from template
   - [ ] Each section has content (not "TBD")
   - [ ] Follows markdown formatting
   ```

---

## Next Steps

After reading this guide, you should:

1. **Review existing instruction files** in `templates/hold/CLAUDE_EXAMPLES/`
   - See how principles are applied in practice
   - Note patterns and structures used

2. **Read the companion documents**:
   - `instruction_file_templates.md` - Ready-to-use templates with variables
   - `instruction_file_generator.md` - Interactive script documentation
   - `role_authority_patterns.md` - Deep dive on decision-making

3. **Try creating a custom instruction file**:
   - Start with simple project (CLI tool)
   - Copy closest existing example
   - Customize for your domain
   - Test with a simple scenario

4. **Iterate and improve**:
   - Run test sessions
   - Observe agent behavior
   - Refine unclear sections
   - Add missing guidance

---

## Appendix: Quick Reference

### Instruction File Checklist

- [ ] Prepended with `ALL_MODELS_TEMPLATE.md` content
- [ ] Role name and phase clearly identified
- [ ] Primary and secondary responsibilities defined
- [ ] Decision authority specified (autonomous, collaborative, escalation)
- [ ] Lead role designated (if applicable)
- [ ] Input and output artifacts listed
- [ ] Workflow phases with checklists
- [ ] Domain-specific guidance included
- [ ] Collaboration protocols defined
- [ ] Examples provided (good and bad)
- [ ] Common pitfalls documented
- [ ] Definition of Done is clear and specific
- [ ] File named correctly: `ROLE_[Name]_[Phase].md`

### Common Sections

Every instruction file should have:
1. Security boundary (from template)
2. Response delimiter protocol (from template)
3. Project completion signal (from template)
4. Role definition
5. Project context
6. Workflow phases
7. Domain-specific guidance
8. Collaboration protocols
9. Common pitfalls
10. Definition of Done

### File Naming

```
ROLE_[RoleName]_[PhaseName].md

Examples:
ROLE_ProductManager_Requirements.md
ROLE_LeadDeveloper_Implementation.md
ROLE_FullStackDeveloper_WebUI.md
```

### Support Documentation

Create these files alongside instruction files:
- `README.md` - Overview of the workflow
- `SESSION_MAPPING.md` - Which roles to use when
- `USER_REQUEST.md` - Example input for Phase 1
- `EXISTING_APP_ANALYSIS.md` - For web UI projects

---

**Questions or Issues?**

- Review existing examples in `templates/hold/CLAUDE_EXAMPLES/`
- Check companion guides (templates, generator, patterns)
- Test with simple projects before complex ones
- Document lessons learned for future reference

---

**Document Metadata**:
- **Author**: Claude Code (Orchestrator Development Team)
- **Version**: 1.0
- **Date**: 2025-11-13
- **Related Docs**:
  - `templates/ALL_MODELS_TEMPLATE.md`
  - `templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/README.md`
  - `instruction_file_templates.md` (to be created)
  - `instruction_file_generator.md` (to be created)
