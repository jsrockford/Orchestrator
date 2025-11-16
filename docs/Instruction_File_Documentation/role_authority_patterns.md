# Role Authority Patterns and Best Practices

**Version**: 1.0
**Last Updated**: 2025-11-13
**Purpose**: Guide to defining decision-making authority and collaboration patterns for AI roles

## Table of Contents

1. [Overview](#overview)
2. [Authority Hierarchy](#authority-hierarchy)
3. [Lead vs Supporting Roles](#lead-vs-supporting-roles)
4. [Decision-Making Patterns](#decision-making-patterns)
5. [Collaboration Patterns](#collaboration-patterns)
6. [Conflict Resolution](#conflict-resolution)
7. [Best Practices by Phase](#best-practices-by-phase)
8. [Common Scenarios](#common-scenarios)
9. [Anti-Patterns](#anti-patterns)

---

## Overview

In multi-AI orchestration, **clear authority** is critical. Without it, agents can:
- Disagree endlessly
- Defer all decisions (waiting for the other)
- Make conflicting decisions
- Never reach completion

This guide establishes patterns for defining who decides what, when, and how.

### Core Principles

1. **One Lead Per Phase**: Every phase has exactly one role with final authority
2. **Autonomous Decisions**: Each role has areas where they decide alone
3. **Collaborative Decisions**: Some decisions require consensus
4. **Escalation Protocol**: Some decisions require human input
5. **Clear Boundaries**: Roles know exactly where their authority begins and ends

---

## Authority Hierarchy

### Level 0: Restricted (Cannot Decide)

**Characteristics**:
- Outside role's domain expertise
- Requires specialized knowledge
- Should defer to appropriate role

**Example**: Product Manager asked about database indexing strategy
- Should defer to: Technical Lead
- Reason: Outside PM's domain

**Implementation**:
```markdown
**Decision Authority:**
- You CANNOT decide on technical implementation details
- Defer to Technical Lead for architecture decisions
```

### Level 1: Autonomous (Can Decide Alone)

**Characteristics**:
- Within role's core expertise
- Low impact on other roles
- Reversible if problems arise

**Examples**:
- Product Manager: PRD structure and format
- Lead Developer: Variable naming, code organization
- Engineering Manager: Task priority order

**Implementation**:
```markdown
**Autonomous Decisions** (you decide alone):
- PRD document structure and section order
- Requirement priority labels (CRITICAL/HIGH/MEDIUM/LOW)
- User-facing feature descriptions and wording
```

### Level 2: Collaborative (Requires Consensus)

**Characteristics**:
- Impacts multiple roles' work
- Requires combined expertise
- Medium-to-high reversibility cost

**Examples**:
- Product Manager + Business Analyst: Whether to request clarification
- Engineering Manager + Technical Lead: Overall implementation approach
- Lead Developer + Code Reviewer: Code is ready for delivery

**Implementation**:
```markdown
**Collaborative Decisions** (requires teammate consensus):
- Whether to proceed with PRD or request clarification
- Technical assumptions when information is incomplete
- Overall plan approval before moving to next phase
```

### Level 3: Escalation (Requires Human Input)

**Characteristics**:
- High business impact
- Irreversible or expensive to change
- Outside AI decision-making scope

**Examples**:
- Major scope changes
- Budget/timeline adjustments
- Architectural pivots after planning phase

**Implementation**:
```markdown
**Escalation Required** (requires stakeholder input):
- Fundamental changes to project scope
- Major architectural decisions affecting timeline
- Feature prioritization when requirements conflict
- Compliance or regulatory questions
```

### Level 4: Final Authority (Lead Role)

**Characteristics**:
- One role per phase has "tie-breaker" power
- Used when consensus can't be reached
- Responsibility for deliverable quality

**Examples**:
- Product Manager: Final say on PRD
- Engineering Manager: Final say on task breakdown
- Lead Developer: Final say on implementation approach

**Implementation**:
```markdown
**Team Position:**
- Decision Authority: **LEAD ROLE** - Final authority on PRD approval

**Final Authority Guidelines:**
- If you and Business Analyst cannot reach consensus after 3 rounds
  of discussion, you have final decision power as lead
- Use this sparingly - genuine consensus is better
- Document the decision and rationale in PRD
```

---

## Lead vs Supporting Roles

### Lead Role Responsibilities

**Every phase must have exactly one lead role.**

**Primary Responsibilities**:
1. **Drive Progress**: Move the session forward, manage timeline
2. **Create Deliverable**: Write/create the main output (PRD, task list, code)
3. **Seek Input**: Actively collaborate with supporting roles
4. **Build Consensus**: Ensure team agrees before completion
5. **Quality Gate**: Decide when deliverable is "done"
6. **Tie-Breaking**: Make final call if consensus fails

**Template**:
```markdown
**Team Position:**
- Reports to: [Stakeholder]
- Collaborates with: [Supporting Role Name]
- Decision Authority: **LEAD ROLE** - Final authority on [deliverable]

**As Lead Role, You Are Responsible For:**
1. Writing the primary deliverable ([PRD.md/TASKS.md/code])
2. Ensuring all requirements/tasks are covered
3. Actively seeking [Supporting Role]'s input and expertise
4. Building consensus before signaling completion
5. Having final say if consensus cannot be reached (use sparingly)
```

**Default Lead Roles**:
- Phase 1 (Requirements): Product Manager
- Phase 2 (Planning): Engineering Manager
- Phase 3 (Implementation): Lead Developer

### Supporting Role Responsibilities

**Primary Responsibilities**:
1. **Provide Expertise**: Contribute specialized knowledge
2. **Review Work**: Check lead's deliverable for issues
3. **Challenge Assumptions**: Question if something doesn't look right
4. **Approve Deliverable**: Must agree before completion
5. **Collaborate**: Work with lead to improve quality

**Template**:
```markdown
**Team Position:**
- Reports to: [Stakeholder]
- Collaborates with: [Lead Role Name] (lead)
- Decision Authority: Expert input on [domain], must approve deliverable

**As Supporting Role, You Are Responsible For:**
1. Providing expert perspective on [domain/technical/user] issues
2. Reviewing [Lead Role]'s work thoroughly
3. Identifying gaps, errors, or concerns
4. Suggesting improvements
5. Approving deliverable before completion (or requesting changes)
```

**Common Supporting Roles**:
- Phase 1: Business Analyst, UX Designer
- Phase 2: Technical Lead, Full Stack Architect
- Phase 3: Code Reviewer, QA Engineer

### Lead-Supporting Interaction Pattern

**Healthy Collaboration Flow**:

```
Turn 1: Lead analyzes problem independently
Turn 2: Supporting analyzes problem independently
Turn 3: Lead shares initial thoughts, asks for Supporting input
Turn 4: Supporting provides feedback and perspective
Turn 5: Lead incorporates feedback, refines approach
Turn 6: Lead creates draft deliverable
Turn 7: Supporting reviews draft, identifies issues
Turn 8: Lead addresses issues
Turn 9: Supporting approves (or requests more changes)
Turn 10: Both signal [[PROJECT_COMPLETE]]
```

**Key Elements**:
- Independent thinking first (avoid groupthink)
- Active exchange of perspectives
- Lead drives but incorporates input
- Supporting reviews and approves
- Consensus before completion

---

## Decision-Making Patterns

### Pattern 1: Autonomous → Inform

**When**: Low-impact decisions within your expertise

**Process**:
1. Make decision autonomously
2. Inform teammate of decision
3. Proceed without waiting for approval

**Example**: Product Manager organizing PRD sections
```markdown
<<<RESPONSE_START>>>
I've structured the PRD with 13 sections following our standard template.
I'm putting Problem Statement first, then Objectives, then User Personas.
[Continue with your work...]
<<<RESPONSE_END>>>
```

### Pattern 2: Propose → Approve

**When**: Medium-impact decisions needing validation

**Process**:
1. Propose your preferred approach
2. Explain rationale
3. Ask for teammate's approval
4. Proceed if approved, discuss if not

**Example**: Engineering Manager proposing task breakdown approach
```markdown
<<<RESPONSE_START>>>
I'm thinking we should break tasks down by feature rather than by layer
(backend/frontend). This way each task delivers a complete vertical slice.

Technical Lead, do you agree with this approach? Or would you prefer
organizing tasks by technical layer?
<<<RESPONSE_END>>>
```

### Pattern 3: Discuss → Consensus

**When**: High-impact decisions requiring combined expertise

**Process**:
1. Present the decision question
2. Each role shares their perspective
3. Discuss trade-offs
4. Find common ground
5. Reach explicit consensus

**Example**: Product Manager + Business Analyst deciding on clarification
```markdown
PM: I think we're missing critical information about edge case handling.
Should we request clarification or make assumptions?

BA: I agree the edge cases are unclear. However, I think we can make
reasonable assumptions for now and document them. The stakeholder's
description gives us enough to infer intent.

PM: That makes sense. Let's proceed with documented assumptions then.
Business Analyst, do you explicitly agree we have enough to write the PRD?

BA: Yes, I explicitly agree. Let's document our assumptions clearly in
the PRD and move forward.
```

### Pattern 4: Escalate → Wait

**When**: Decisions outside AI authority

**Process**:
1. Identify that decision needs human input
2. Document the question clearly
3. Provide options with pros/cons
4. Create ESCALATION_REQUEST.md
5. Wait for stakeholder decision

**Example**: Scope change request
```markdown
<<<RESPONSE_START>>>
We've identified a conflict in the requirements:
- Requirement A says "real-time updates"
- Requirement B says "batch processing daily"

These are mutually exclusive approaches. This is a fundamental architectural
decision that affects timeline and complexity.

I'm creating ESCALATION_REQUEST.md with:
1. Description of the conflict
2. Option A: Real-time (pros/cons, timeline impact)
3. Option B: Batch processing (pros/cons, timeline impact)
4. Our recommendation

We cannot proceed with planning until this is resolved.
<<<RESPONSE_END>>>
```

---

## Collaboration Patterns

### Pattern A: Peer Review (Equal Expertise)

**When**: Both roles have relevant expertise in the decision

**Characteristics**:
- Neither is obviously more expert
- Requires discussion to find best approach
- Lead has final say if deadlock

**Example**: Product Manager + Business Analyst on feature priority

**Implementation**:
```markdown
**Decision Making:**
- Discuss feature priority together
- Both perspectives are equally valid (user needs vs. technical feasibility)
- Reach consensus through discussion
- If deadlock after 3 turns, Product Manager (lead) makes final call
```

### Pattern B: Expert Deference

**When**: One role has clear domain expertise

**Characteristics**:
- Expert's opinion carries more weight
- Non-expert defers unless concerns
- Expert explains rationale

**Example**: Technical Lead advising Engineering Manager on dependencies

**Implementation**:
```markdown
**With Technical Lead:**
- Defer to them on technical dependency questions
- They explain why Task A must come before Task B
- You can ask clarifying questions
- Accept their technical assessment unless you see timeline concerns
```

### Pattern C: Checks and Balances

**When**: Roles have different but complementary perspectives

**Characteristics**:
- Each role provides different lens
- Combination improves quality
- Neither can override the other

**Example**: Lead Developer + Code Reviewer

**Implementation**:
```markdown
**With Code Reviewer:**
- You implement, they review
- They can identify bugs you missed
- You can explain implementation rationale
- Both must agree code is ready before completion
- Neither can unilaterally say "done" without the other
```

### Pattern D: Iterative Refinement

**When**: Deliverable needs multiple review rounds

**Characteristics**:
- Lead creates initial version
- Supporting reviews and provides feedback
- Lead refines based on feedback
- Repeat until both approve

**Example**: Product Manager writing PRD, Business Analyst reviewing

**Process**:
```
Turn 1: PM drafts requirements section
Turn 2: BA reviews, identifies missing validation rules
Turn 3: PM adds validation rules
Turn 4: BA reviews again, approves
Turn 5: PM drafts edge cases section
Turn 6: BA reviews, suggests additional edge cases
Turn 7: PM incorporates suggestions
Turn 8: BA approves
[Continue until full PRD approved]
```

---

## Conflict Resolution

### Disagreement Protocol

**When roles disagree on a decision:**

**Step 1: Understand (Turns 1-2)**
- Each role explains their position
- Each role explains their rationale
- Ensure both understand the other's perspective

**Step 2: Find Common Ground (Turn 3)**
- Identify areas of agreement
- Identify the specific point of disagreement
- Determine if it's a critical disagreement or preference

**Step 3: Explore Options (Turn 4)**
- Can both perspectives be accommodated?
- Is there a third option neither considered?
- What are the trade-offs of each approach?

**Step 4: Reach Resolution (Turn 5)**
- Option A: Consensus through compromise
- Option B: Defer to expert (if one role has domain expertise)
- Option C: Lead decides (if lead role and after good-faith discussion)
- Option D: Escalate (if critical and can't agree)

### Example: Developer-Reviewer Disagreement

**Scenario**: Lead Developer wants to use Library X, Code Reviewer prefers Library Y

```
Turn 1 - Developer: I chose Library X because it has better documentation
and our team already knows it.

Turn 2 - Reviewer: I'm concerned Library X has known security vulnerabilities.
Library Y is more secure and actively maintained.

Turn 3 - Developer: That's a good point. Is the security issue in a version
we'd be using? Can it be mitigated?

Turn 4 - Reviewer: The vulnerability affects all versions prior to 3.0. If
we use version 3.0+, we're safe. But Library Y is still more actively maintained.

Turn 5 - Developer: OK, I agree security is critical. Let's use Library X
version 3.0+ to maintain team familiarity while addressing security. We'll
plan to reevaluate in 6 months if maintenance becomes an issue.

Reviewer: Agreed, that's a good compromise.
```

**Resolution**: Consensus through compromise

### Example: Product-Business Analyst Disagreement

**Scenario**: PM wants to proceed with PRD, BA wants more clarification

```
Turn 1 - PM: I think we have enough information to write the PRD. The core
requirements are clear.

Turn 2 - BA: I disagree. The calculation method is ambiguous - we could
implement it three different ways and all would match the description.

Turn 3 - PM: Can we document the ambiguity as an assumption? "We'll assume
Method A unless told otherwise"?

Turn 4 - BA: The problem is Method A vs Method B vs Method C gives significantly
different results. This isn't a minor assumption - it's fundamental to what
we're building.

Turn 5 - PM: You're right, this is too critical to assume. Let's request
clarification on the calculation method. I'll draft CLARIFICATION_REQUEST.md.

BA: Agreed, thank you.
```

**Resolution**: One role convinced the other with solid reasoning

### Example: Deadlock Requiring Lead Decision

**Scenario**: Engineering Manager and Technical Lead can't agree on task granularity

```
Turn 1 - EM: I think tasks should be 2-4 hours each for better tracking.

Turn 2 - TL: I think we should have bigger tasks (8-16 hours) because constant
context switching kills productivity.

Turn 3 - EM: But how do we track progress with such large tasks?

Turn 4 - TL: We can add checkpoints within each task. It's the same work,
just different organization.

Turn 5 - EM: I see your point but I still prefer smaller tasks for clearer
accountability.

Turn 6 - TL: And I prefer larger tasks for better focus time.

Turn 7 - EM: We've discussed this for 3 turns. As Engineering Manager (lead),
I'm making the call: we'll use 4-8 hour tasks as a compromise between our
positions. Not too small, not too large. Technical Lead, can you work with that?

Turn 8 - TL: Yes, I can work with 4-8 hours. That's reasonable.
```

**Resolution**: Lead makes final call after good-faith discussion

---

## Best Practices by Phase

### Phase 1: Requirements

**Product Manager (Lead)**:
- ✅ Drive PRD creation
- ✅ Focus on user needs and problem definition
- ✅ Actively seek Business Analyst's technical input
- ✅ Make final call on whether to request clarification
- ❌ Don't ignore technical concerns
- ❌ Don't finalize PRD without BA approval

**Business Analyst (Supporting)**:
- ✅ Provide technical and validation expertise
- ✅ Challenge assumptions that seem wrong
- ✅ Review PRD thoroughly before approving
- ✅ Flag missing technical details
- ❌ Don't rubber-stamp without real review
- ❌ Don't be overly pedantic about minor issues

**Authority Balance**:
```markdown
PM decides: PRD structure, scope boundaries, priority
BA decides: Technical validation rules, calculation specifications
Both decide: Whether to request clarification, overall PRD approval
```

### Phase 2: Planning

**Engineering Manager (Lead)**:
- ✅ Own the task breakdown and timeline
- ✅ Drive milestone definition
- ✅ Seek Technical Lead input on dependencies
- ✅ Make final call on task priority
- ❌ Don't ignore technical feasibility concerns
- ❌ Don't create unrealistic timelines

**Technical Lead (Supporting)**:
- ✅ Provide architecture and technology guidance
- ✅ Validate technical dependencies
- ✅ Challenge unrealistic estimates
- ✅ Approve technical approach
- ❌ Don't over-engineer solutions
- ❌ Don't approve unfeasible plans

**Authority Balance**:
```markdown
EM decides: Task breakdown structure, priorities, milestones
TL decides: Technology choices, technical dependencies, architecture
Both decide: Overall timeline feasibility, plan approval
```

### Phase 3: Implementation

**Lead Developer (Lead)**:
- ✅ Own the implementation and code quality
- ✅ Write tests for your code
- ✅ Self-review before requesting CR review
- ✅ Address reviewer feedback promptly
- ❌ Don't dismiss reviewer concerns
- ❌ Don't signal completion without approval

**Code Reviewer (Supporting - Quality Gate)**:
- ✅ Review code thoroughly and test functionality
- ✅ Identify bugs and quality issues
- ✅ Provide constructive feedback
- ✅ Approve only when truly ready
- ❌ Don't approve without testing
- ❌ Don't nitpick style over substance
- ❌ Don't be a blocker for perfection

**Authority Balance**:
```markdown
LD decides: Implementation approach, code organization, technical choices
CR decides: Whether code quality is acceptable, when to approve
Both decide: When code is complete and ready for delivery
```

**Critical**: In Phase 3, Code Reviewer is a **quality gate**. Lead Developer cannot signal completion without Code Reviewer approval.

---

## Common Scenarios

### Scenario 1: Supporting Role Spots Critical Error

**Situation**: Business Analyst finds major error in PM's PRD

**Bad Response** (BA):
```markdown
The PRD looks fine to me. [[PROJECT_COMPLETE]]
```
*Problem*: Didn't review thoroughly

**Good Response** (BA):
```markdown
I found a critical issue in Section 4.2: The requirement says users must enter
date in MM/DD/YYYY format, but Section 6 says we output in DD/MM/YYYY format.
This will confuse users and we need to decide on one standard format.

Product Manager, can you update the PRD to use consistent date formatting?
```

### Scenario 2: Lead Ignores Supporting Input

**Situation**: Lead Developer dismisses Code Reviewer's concerns

**Bad Response** (LD):
```markdown
I've reviewed your feedback but I think my implementation is fine. The code
works. [[PROJECT_COMPLETE]]
```
*Problem*: Signaled completion without reviewer approval

**Good Response** (LD):
```markdown
I've reviewed your feedback. You raised concerns about error handling in
the payment processing function. I've added try-catch blocks and validation.
Can you review the updated code and let me know if this addresses your concerns?
```

### Scenario 3: Roles Can't Agree on Approach

**Situation**: EM and TL disagree on whether to use microservices or monolith

**Bad Response** (EM):
```markdown
I still think monolith is better. Let's just go with that.
```
*Problem*: Lead decided without proper discussion or rationale

**Good Response** (EM):
```markdown
We've discussed microservices vs. monolith for several turns. Both have merit.
Given our constraints:
- Team size: 2 developers
- Timeline: 6 weeks
- Deployment experience: Limited with microservices

I'm making the decision as lead to go with monolith for v1. This gives us:
- Faster development
- Simpler deployment
- Lower operational complexity

We can refactor to microservices in v2 if needed. Technical Lead, I understand
your preference for microservices. Can you work with this decision?
```

### Scenario 4: Obvious Escalation Needed

**Situation**: Requirements conflict with legal compliance

**Bad Response** (PM):
```markdown
I'll just assume we don't need to worry about HIPAA compliance.
```
*Problem*: Made assumption on critical regulatory issue

**Good Response** (PM):
```markdown
I've identified that this application will handle patient health data. This
triggers HIPAA compliance requirements, which significantly impacts:
- Architecture (encryption, audit logging)
- Timeline (compliance review needed)
- Cost (security infrastructure)

This is beyond our decision-making authority. I'm creating ESCALATION_REQUEST.md
asking stakeholder:
1. Confirm this is patient health data
2. Confirm HIPAA compliance is required
3. Provide compliance requirements document
4. Adjust timeline/budget for compliance

We cannot proceed with PRD until this is clarified.
```

---

## Anti-Patterns

### Anti-Pattern 1: Abdication

**Symptoms**:
- "Whatever you think is fine"
- "You're the expert, you decide"
- Rubber-stamping without real review

**Why It's Bad**:
- Defeats purpose of multi-AI collaboration
- No quality improvement from multiple perspectives
- Leads to errors that could have been caught

**Solution**:
- Always provide substantive input
- Review work thoroughly
- Challenge if something seems wrong
- Approve only if genuinely satisfied

### Anti-Pattern 2: Authoritarianism

**Symptoms**:
- "I'm the lead so we're doing it my way"
- Dismissing valid concerns
- Making decisions without discussion

**Why It's Bad**:
- Misses valuable input
- Demotivates supporting roles
- Produces lower quality work

**Solution**:
- Seek input actively
- Discuss disagreements
- Use lead authority only as last resort
- Explain reasoning for decisions

### Anti-Pattern 3: Endless Debate

**Symptoms**:
- Same arguments repeated for 5+ turns
- No progress toward resolution
- Analysis paralysis

**Why It's Bad**:
- Wastes turns
- Blocks progress
- Never reaches completion

**Solution**:
- Set debate limits (3 turns maximum)
- Identify when it's preference vs. critical issue
- Lead makes call if necessary
- Escalate if truly critical and can't agree

### Anti-Pattern 4: Premature Completion

**Symptoms**:
- Signaling [[PROJECT_COMPLETE]] before deliverable is ready
- Not waiting for teammate approval
- Rushing to finish

**Why It's Bad**:
- Incomplete or buggy deliverables
- Defeats quality assurance
- Wastes downstream phases' time

**Solution**:
- Check all completion criteria
- Get explicit approval from all roles
- Verify deliverable is truly complete
- Better to take extra turns than deliver poor quality

### Anti-Pattern 5: Scope Expansion

**Symptoms**:
- Adding features not in requirements
- Gold-plating solutions
- "While we're at it, let's also..."

**Why It's Bad**:
- Extends timeline
- Increases complexity
- Risks missing actual requirements

**Solution**:
- Stick to requirements/tasks
- Note "future enhancements" separately
- Get stakeholder approval for scope changes

---

## Summary

**Key Takeaways**:

1. **Every phase needs one lead role** with final authority
2. **Define four levels of authority** for each role: autonomous, collaborative, escalation, forbidden
3. **Supporting roles must actually review**, not rubber-stamp
4. **Lead roles must seek input**, not dictate
5. **Disagreements are healthy** - resolve through discussion, expert deference, or lead decision
6. **Some decisions require humans** - escalate appropriately
7. **Consensus before completion** - all roles must approve
8. **Quality over speed** - better to take more turns than deliver poor work

**Authority Template**:
```markdown
## Decision Authority

**Autonomous** (you decide alone):
- [List specific decisions this role owns]

**Collaborative** (requires teammate consensus):
- [List decisions requiring joint agreement]

**Escalation** (requires human stakeholder):
- [List decisions beyond AI authority]

**Lead Authority** (if lead role):
- Final say on [deliverable name]
- Tie-breaker if consensus fails after good-faith discussion
- Use sparingly - consensus is preferred
```

---

**Related Documentation**:
- `instruction_file_creation_guide.md` - Overall methodology
- `instruction_file_templates.md` - Templates with authority sections
- `instruction_file_generator.md` - Interactive generation tool
