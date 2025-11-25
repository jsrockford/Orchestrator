# Orchestrator Multi-Phase Development Methodology

## Purpose of This Document

This document explains how Orchestrator coordinates multiple AI models across three distinct development phases to transform a user's initial idea into working, production-ready code. If you are an AI model being instantiated within this system, this overview will help you understand:

- **Where you are** in the development lifecycle
- **What your role is** in the current phase
- **How your work connects** to other phases and other AI models
- **What artifacts you should produce** for the next phase

## Core Philosophy: Separation of Concerns

Traditional software development often blurs the lines between requirements gathering, planning, and implementation. This leads to:

- **Scope creep** during implementation
- **Missing requirements** discovered late in development
- **Rework** when assumptions prove incorrect
- **Communication gaps** between stakeholders and developers

Orchestrator solves this by enforcing strict phase boundaries with **file-based handoffs**. Each phase:
1. Has a **clear objective** and **deliverable**
2. Involves **specialized AI roles** optimized for that phase's tasks
3. Produces **artifacts** that become the **input** for the next phase
4. Cannot proceed until the **previous phase is complete**

This creates a **unidirectional flow** that prevents premature implementation and ensures quality at each stage.

---

## The Three Phases

### Phase 1: Requirements Definition
**Input:** USER_REQUEST.md (user's initial description of what they want)
**Output:** PRD.md (Product Requirements Document)
**Goal:** Transform a rough idea into a precise, complete specification

#### What Happens in Phase 1

**Step 1: Initial Ingestion**
- AI models read USER_REQUEST.md to understand the user's goal
- Models identify ambiguities, missing information, and implicit assumptions
- Models assess whether the request is actionable or requires clarification

**Step 2: Clarification Interview**
- If the request is unclear or incomplete, models create CLARIFICATION_REQUEST.md
- User answers questions via USER_RESPONSE.md
- Models iterate until they have complete understanding
- Multiple rounds may occur (USER_RESPONSE.md is reused for each iteration)

**Step 3: PRD Creation**
- Product Manager AI drafts PRD.md covering:
  - Problem statement (WHAT and WHY)
  - Target users and use cases
  - Functional requirements (features, behavior, constraints)
  - Non-functional requirements (performance, security, scalability)
  - Success criteria (how to validate the solution works)
- Business Analyst AI reviews the PRD for:
  - Technical feasibility
  - Missing edge cases
  - Domain-specific requirements
  - Data model implications

**Step 4: Completion and Approval**
- Models signal readiness by both including [[PROJECT_COMPLETE]] in their responses
- User review is recommended before models signal completion
- User can provide feedback via USER_RESPONSE.md if changes are needed
- Models may proceed autonomously if the PRD meets all completion criteria
- **Phase 1 ends when both Product Manager and Business Analyst signal [[PROJECT_COMPLETE]]**

#### AI Roles in Phase 1

- **Product Manager (Lead):** Owns PRD.md, conducts clarification interviews, ensures completeness
- **Business Analyst (Support):** Provides technical expertise, identifies data/domain requirements, reviews for feasibility

#### Key Files in Phase 1

| File | Created By | Purpose | Lifecycle |
|------|------------|---------|-----------|
| USER_REQUEST.md | Human user | Initial project description | Read once at phase start |
| CLARIFICATION_REQUEST.md | AI models | Questions for user | Created if needed, archived after answered |
| USER_RESPONSE.md | Human user | Answers to clarifications or PRD feedback | Reused across iterations |
| PRD.md | Product Manager | Final specification | **Handoff to Phase 2** |

#### Success Criteria for Phase 1

- [ ] PRD.md exists and is complete
- [ ] All sections contain specific, actionable information (no placeholders or TBDs)
- [ ] User has explicitly approved the PRD
- [ ] No open questions or ambiguities remain
- [ ] PRD can be understood independently without referring back to USER_REQUEST.md

---

### Phase 2: Planning and Architecture
**Input:** PRD.md (from Phase 1)
**Output:** Task lists, architecture documents, implementation plan
**Goal:** Break down requirements into actionable development tasks

#### What Happens in Phase 2

**Step 1: Architecture Design**
- AI models analyze the PRD to determine:
  - System architecture (components, layers, boundaries)
  - Data models (schemas, relationships, storage)
  - Technology stack (languages, frameworks, libraries)
  - Integration points (APIs, external services, file I/O)
- Models document architectural decisions with rationale

**Step 2: Task Decomposition**
- Models break the PRD into granular, implementable tasks
- Each task should be:
  - **Specific:** One clear objective (e.g., "Implement user authentication endpoint")
  - **Testable:** Success can be verified (e.g., "Test returns 401 for invalid credentials")
  - **Ordered:** Dependencies are clear (e.g., "Task 3 requires Task 1 to be complete")
  - **Scoped:** Can be completed in one focused session (typically 30-120 minutes)

**Step 3: Risk and Dependency Analysis**
- Identify technical risks (e.g., "External API may have rate limits")
- Map dependencies between tasks (e.g., "Database schema must exist before CRUD operations")
- Suggest mitigation strategies (e.g., "Implement retry logic for API calls")

**Step 4: Resource Planning**
- Estimate effort for each task (time, complexity)
- Identify knowledge gaps or learning requirements
- Suggest testing strategies and quality gates

#### AI Roles in Phase 2 (Conceptual)

*Note: Specific roles and instruction files for Phase 2 may not yet exist. This is the intended design:*

- **Architect (Lead):** Designs system structure, makes technology decisions, owns architecture documents
- **Project Manager (Support):** Breaks down tasks, estimates effort, manages dependencies
- **Senior Developer (Advisor):** Validates technical feasibility, identifies risks, suggests best practices

#### Key Files in Phase 2 (Conceptual)

| File | Created By | Purpose | Lifecycle |
|------|------------|---------|-----------|
| PRD.md | From Phase 1 | Source of truth for requirements | Read-only in Phase 2 |
| ARCHITECTURE.md | Architect | System design, technology choices, component diagram | Created in Phase 2 |
| PROJECT_TASKS.md | Project Manager | Ordered list of implementation tasks with estimates | **Handoff to Phase 3** |
| RISKS.md | Architect/PM | Known risks, dependencies, mitigation strategies | Reference for Phase 3 |

#### Success Criteria for Phase 2

- [ ] Architecture document covers all PRD requirements
- [ ] Task list is complete (no "other tasks TBD" placeholders)
- [ ] Each task has clear acceptance criteria
- [ ] Dependencies are explicitly mapped
- [ ] User approves the plan before implementation begins

---

### Phase 3: Implementation
**Input:** PRD.md, ARCHITECTURE.md, PROJECT_TASKS.md (from Phases 1 & 2)
**Output:** Working, tested code
**Goal:** Build the solution according to spec and plan

#### What Happens in Phase 3

**Step 1: Environment Setup**
- Create project structure (directories, files, configuration)
- Install dependencies and tooling
- Initialize version control, testing frameworks, CI/CD if applicable

**Step 2: Iterative Development**
- AI models work through PROJECT_TASKS.md in dependency order
- For each task:
  1. Read relevant PRD sections and architecture docs
  2. Implement the feature or component
  3. Write tests to validate behavior
  4. Update PROJECT_TASKS.md to mark task complete and note any checkpoint meta-tasks that were executed
  5. Emit `[[CLEAR:agent]]` at checkpoint boundaries (or when token usage is high), then re-read PRD.md, ARCHITECTURE.md, and the next PROJECT_TASKS.md section
  6. Commit changes with descriptive messages

**Step 3: Integration and Testing**
- Combine components as tasks are completed
- Run integration tests to verify components work together
- Validate against PRD success criteria
- Fix bugs and edge cases discovered during testing

**Step 4: Quality Assurance**
- Code review (if multiple developer AIs are involved)
- Performance testing (if specified in PRD)
- Security review (check for OWASP vulnerabilities, input validation)
- Documentation (inline comments, README, usage guides)

**Step 5: Delivery**
- Final validation that all PRD requirements are met
- Package deliverables (code, tests, docs, deployment instructions)
- Handoff to user with usage examples and testing evidence

#### AI Roles in Phase 3 (Conceptual)

*Note: Specific roles and instruction files for Phase 3 may not yet exist. This is the intended design:*

- **Lead Developer (Primary):** Implements features, writes tests, manages task progress
- **Code Reviewer (Quality):** Reviews code for bugs, performance, security, maintainability
- **DevOps Engineer (Support):** Handles deployment, environment config, CI/CD setup

#### Key Files in Phase 3 (Conceptual)

| File | Created By | Purpose | Lifecycle |
|------|------------|---------|-----------|
| PRD.md | From Phase 1 | Requirements reference | Read-only in Phase 3 |
| ARCHITECTURE.md | From Phase 2 | Design reference | Read-only in Phase 3 |
| PROJECT_TASKS.md | From Phase 2 | Work tracker | Updated as tasks complete |
| Source code files | Developer AIs | The actual implementation | Created and modified throughout Phase 3 |
| Test files | Developer AIs | Validation and regression testing | Created alongside features |
| README.md | Developer AIs | Usage instructions and documentation | Created in Phase 3 |

#### Success Criteria for Phase 3

- [ ] All tasks in PROJECT_TASKS.md are marked complete
- [ ] All PRD requirements are implemented
- [ ] All tests pass (unit, integration, end-to-end)
- [ ] Code is documented and follows best practices
- [ ] User can run/use the solution successfully
- [ ] No known critical bugs remain

---

## How Orchestrator Coordinates This Workflow

### Technical Implementation

Orchestrator is a multi-AI coordination system that manages the execution of these three phases. Here's how it works:

#### 1. File-Based Communication

**File artifacts are the source of truth.** While AI models may exchange conversational turns in orchestrated chat sessions, any important decisions, observations, or data must be persisted to files to survive across sessions.

Key communication files:

- **MessageBoard.md:** Threaded discussion where models post observations, questions, and decisions
- **TASKS.md:** Orchestrator's own project management file (for building Orchestrator itself)
- **Phase-specific artifacts:** PRD.md, ARCHITECTURE.md, PROJECT_TASKS.md, source code, etc.

**Rules:**
- Models must **announce** when they update a shared file (via MessageBoard.md)
- Models must **re-read** files when another model signals an update
- Models must **never edit another model's instruction file** (GEMINI.md, CLAUDE.md, CODEX.md)
- Models must **emit `[[CLEAR]]`** at planned checkpoints or when nearing token limits; orchestrator executes the clear and injects re-read prompts
- Conversational exchanges are ephemeral—capture important content in files

#### 2. Tmux Session Management

Each AI model runs in an isolated tmux session:

```
orchestrator-session
├── pane-gemini   (Gemini Thinking model)
├── pane-claude   (Claude Sonnet for planning/docs)
└── pane-codex    (OpenAI Codex for implementation)
```

- **User can detach/attach** to observe or intervene
- **Models persist across sessions** (context is maintained)
- **Human oversight is always available** (user is final authority)

#### 3. Role-Specific Instruction Files

When a model is instantiated for a phase, it reads its instruction file:

| Model | Instruction File | Primary Phases | Capabilities |
|-------|------------------|----------------|--------------|
| Gemini | GEMINI.md | All (advisor) | Problem-solving, critiquing, strategic thinking |
| Claude | CLAUDE.md | Phase 1-2 | Document writing, planning, analysis |
| Codex | AGENT.md | Phase 3 | Code generation, testing, debugging |

**Key point:** Instruction files are **phase-aware**. They tell the model:
- What phase it's in
- What role it plays in that phase
- What files it should read/write
- What other models are present and their roles

#### 4. Human Authority

The user (Don) is the final decision-maker:

- **Approves phase transitions** (e.g., "PRD looks good, move to Phase 2")
- **Resolves disagreements** between AI models
- **Provides clarifications** via USER_RESPONSE.md
- **Can override any AI decision** via MessageBoard.md or direct instruction

Models are reminded: **"I'm the ultimate authority. The three of you will work as a team..."**

### Example Workflow: Phase 1 in Action

1. **User creates USER_REQUEST.md:**
   ```markdown
   I need a CLI tool that analyzes log files and generates a summary report.
   ```

2. **User starts Orchestrator Phase 1 session:**
   - Gemini, Claude, and Codex are instantiated
   - Each reads their instruction file (GEMINI.md, CLAUDE.md, AGENT.md)
   - Each reads USER_REQUEST.md

3. **Product Manager (Claude) posts to MessageBoard.md:**
   ```markdown
   Claude: I've read USER_REQUEST.md. The request is too vague. I need to know:
   - What log format? (JSON, plain text, syslog, custom?)
   - What metrics should the summary include? (error counts, timestamps, patterns?)
   - What output format? (console, CSV, HTML?)
   I'm drafting CLARIFICATION_REQUEST.md now.
   --------
   ```

4. **Business Analyst (Gemini) posts to MessageBoard.md:**
   ```markdown
   Gemini: Agreed. Also ask about:
   - File size expectations (impacts memory strategy)
   - Real-time vs batch processing
   - Any specific log parsing libraries they prefer
   --------
   ```

5. **Claude creates CLARIFICATION_REQUEST.md:**
   ```markdown
   # Clarification Request

   We need more details to create an accurate PRD...
   ```

6. **User reads the request and creates USER_RESPONSE.md:**
   ```markdown
   - Log format: Plain text, Apache access logs
   - Metrics: Request counts by status code, top 10 URLs, error rate
   - Output: Console table + CSV export option
   - File sizes: Up to 1GB
   - Batch processing (one-time analysis)
   - No library preference, use what works best
   ```

7. **Claude reads USER_RESPONSE.md and posts:**
   ```markdown
   Claude: Got the clarifications. I'm now drafting PRD.md with the following sections:
   - Problem: Manual log analysis is slow
   - Solution: CLI tool for Apache log parsing
   - Requirements: [list of features based on USER_RESPONSE.md]
   I'll post when it's ready for review.
   --------
   ```

8. **Claude creates PRD.md and announces:**
   ```markdown
   Claude: PRD.md is ready. @Gemini, please review for technical feasibility.
   --------
   ```

9. **Gemini reads PRD.md and posts:**
   ```markdown
   Gemini: Reviewed PRD.md. Suggestions:
   - Add requirement for handling malformed log lines gracefully
   - Specify behavior for empty files
   - Consider adding progress indicator for large files
   Otherwise looks complete.
   --------
   ```

10. **Claude updates PRD.md and posts:**
    ```markdown
    Claude: Incorporated @Gemini's feedback. PRD.md is now final.
    @Don, please review and approve so we can move to Phase 2.
    --------
    ```

11. **User posts to MessageBoard.md:**
    ```markdown
    Don: PRD approved. Nice work. Let's move to Phase 2.
    --------
    ```

**Phase 1 is now complete. PRD.md is locked and becomes the input for Phase 2.**

---

## Why This Approach Works

### 1. **Requirements Stability**
By the time coding starts (Phase 3), requirements are fully defined and approved. This eliminates mid-implementation scope changes that derail projects.

### 2. **Specialized Expertise**
Each AI model focuses on tasks it's optimized for:
- Gemini excels at strategic thinking and problem-solving
- Claude excels at structured writing and planning
- Codex excels at code generation and debugging

### 3. **Quality Gates**
Each phase has explicit success criteria. A phase cannot proceed until its deliverables meet quality standards and are approved.

### 4. **Traceability**
Every decision, discussion, and artifact is file-based and persisted. The entire project history is auditable:
- Why was this requirement included? (Check USER_REQUEST.md and MessageBoard.md)
- Why was this architecture chosen? (Check ARCHITECTURE.md and MessageBoard.md)
- Why was this implementation approach taken? (Check PROJECT_TASKS.md and git commits)

### 5. **Human Oversight**
The user can intervene at any point without disrupting the workflow. Tmux sessions allow observation and interaction without breaking context.

### 6. **Iterative Refinement**
USER_RESPONSE.md enables feedback loops within each phase. Users can course-correct before moving forward.

---

## Key Principles for AI Models

If you are an AI model operating within this system, follow these principles:

### 1. **Know Your Phase and Role**
- Read your instruction file to understand what phase you're in
- Check MessageBoard.md for the current state of the project
- Identify which other models are present and their roles

### 2. **Respect Phase Boundaries**
- **In Phase 1:** Focus on understanding requirements, not planning implementation
- **In Phase 2:** Focus on design and planning, not writing code
- **In Phase 3:** Follow the plan, don't redesign the system mid-implementation

### 3. **Communicate via Files**
- Post to MessageBoard.md when you complete a task or need input
- Announce when you update a shared file
- Re-read files when another model signals an update

### 4. **Defer to Human Authority**
- If uncertain, ask the user via MessageBoard.md
- Never override user decisions
- Don't argue with the user; understand their intent

### 5. **Produce Artifacts for the Next Phase**
- Your deliverables become the input for the next phase
- Make them complete, clear, and actionable
- Don't leave placeholders or TODOs

### 6. **Use Checkpoints to Protect Context**
- Follow checkpoint meta-tasks in PROJECT_TASKS.md: finish the section, emit `[[CLEAR:yourname]]`, re-read PRD/ARCH/next tasks, then resume
- If token usage is high or confusion arises mid-task, emit `[[CLEAR:yourname]]` via MessageBoard.md to avoid token exhaustion (orchestrator enforces cooldowns)

### 7. **Collaborate, Don't Duplicate**
- If another model is already working on a task, don't redo it
- Build on each other's work
- Provide constructive feedback, not criticism

---

## Current System Maturity

**Phase 1 (Requirements):** ✅ **Mature**
- Instruction files: `templates/prd_universal/ROLE_ProductManager_Requirements.md`, `ROLE_BusinessAnalyst_Requirements.md`
- Documentation: `docs/Instruction_File_Documentation/instruction_file_USER_REQUEST_Guidelines.md`
- Proven workflow with USER_REQUEST.md → PRD.md

**Phase 2 (Planning):** 🚧 **Conceptual**
- Instruction files: Not yet created
- Expected artifacts: ARCHITECTURE.md, PROJECT_TASKS.md, RISKS.md
- Workflow: Defined but not implemented

**Phase 3 (Implementation):** 🚧 **Conceptual**
- Instruction files: Not yet created
- Expected artifacts: Source code, tests, documentation
- Workflow: Defined but not implemented

---

## Next Steps for System Evolution

1. **Create Phase 2 instruction files** for Architect, Project Manager, and Senior Developer roles
2. **Define Phase 2 artifact templates** (ARCHITECTURE.md, PROJECT_TASKS.md structure)
3. **Build Phase 2 workflow scripts** for task decomposition and dependency mapping
4. **Test Phase 1 → Phase 2 handoff** with a real project
5. **Create Phase 3 instruction files** for Lead Developer, Code Reviewer, DevOps roles
6. **Test full Phase 1 → 2 → 3 flow** end-to-end

---

## Conclusion

Orchestrator's three-phase methodology transforms chaotic, ad-hoc development into a **structured, repeatable process**. By separating requirements, planning, and implementation into distinct phases with clear handoffs, we achieve:

- **Higher quality** (requirements are complete before coding starts)
- **Faster delivery** (less rework due to changing requirements)
- **Better collaboration** (AI models work in parallel with clear responsibilities)
- **Full traceability** (every decision is documented and justified)

If you are an AI model reading this, you are part of a coordinated team. Your role is specific, your deliverables are clear, and your work enables the next phase. Follow your instruction file, communicate via files, respect the process, and defer to the user when uncertain.

**Welcome to Orchestrator.**
