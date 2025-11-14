# Instruction Generator Implementation Notes

**Version**: 2.1 (Defaults-Based Generation with Definition of Done)
**Last Updated**: 2025-11-14
**Status**: Active Development

---

## Table of Contents

1. [Overview](#overview)
2. [Evolution: From TODOs to Defaults](#evolution-from-todos-to-defaults)
3. [Architecture](#architecture)
4. [Default Dictionaries](#default-dictionaries)
5. [Automation Levels](#automation-levels)
6. [Testing & Refinement](#testing--refinement)
7. [Future Enhancements](#future-enhancements)
8. [Change Log](#change-log)

---

## Overview

The instruction file generator (`scripts/generate_instruction_files.py`) is a Python script that automates the creation of role-specific instruction files for multi-AI orchestration sessions.

### Purpose

- **Reduce manual effort**: Minimize TODO markers in generated files
- **Maintain consistency**: Ensure all projects follow established patterns
- **Enable rapid iteration**: Quickly generate instruction files for new projects
- **Support refinement**: Auto-fill additional content as artifacts become available

### Three-Stage Generation Process

1. **Stage 1 (Initial)**: Interview-based generation with role/phase defaults
2. **Stage 2 (Phase 2 Refinement)**: PRD-based auto-filling of Planning templates
3. **Stage 3 (Phase 3 Refinement)**: ARCHITECTURE-based filling (planned, not yet implemented)

---

## Evolution: From TODOs to Defaults

### Version 1.0 (Original Approach)

**Problem**: Generated files had ~15 TODOs per file requiring manual completion

**Example Output**:
```markdown
**Primary Responsibilities:**
- [TODO: Customize for EngineeringManager role]
- [Add specific responsibilities]

**Decision Authority:**
- **LEAD ROLE** - [TODO: Define authority level]
```

**User Feedback**: "Most projects follow the same patterns. Why can't these be defaults?"

### Version 2.0 (Defaults-Based Approach)

**Solution**: Extract common patterns into default dictionaries and auto-fill during generation

**Example Output**:
```markdown
**Primary Responsibilities:**
- Break down PRD requirements into specific, actionable development tasks
- Create comprehensive task breakdown with clear dependencies
- Estimate effort and define realistic timeline
- Identify project risks and mitigation strategies
- Create PROJECT_TASKS.md as primary deliverable
- Ensure all PRD requirements are covered by tasks

**Decision Authority:**
- **LEAD ROLE** - Final say on task breakdown structure, priorities, milestone definitions, and timeline estimates
```

**Result**: Reduced from ~15 TODOs to ~2-3 TODOs per file (only Domain + Tech guidance remain)

---

## Architecture

### Core Components

```
scripts/generate_instruction_files.py
├── ROLE_DEFAULTS          # Common responsibilities for each role
├── PHASE_WORKFLOWS        # Standard workflow for each phase
├── COLLABORATION_PATTERNS # How role pairs work together
├── InstructionFileGenerator
│   ├── _interview_user()           # Gather project info
│   ├── _generate_instruction_files() # Create files
│   ├── _get_role_template()        # Build content from defaults
│   └── refine_templates()          # Stage 2+ refinement
└── CLI argument parsing
```

### Key Design Decisions

1. **First role in list is always lead**: Simplifies authority assignment
2. **Role-based defaults**: Each role has consistent responsibilities across projects
3. **Phase-based workflows**: Requirements/Planning/Implementation have standard flows
4. **Role-pair patterns**: Common collaborations (PM+BA, EM+TL, LD+CR) have defined dynamics
5. **Definition of Done defaults**: Phase-specific completion criteria auto-filled
6. **Template variables remain for domain/tech**: Cannot be genericized

---

## Default Dictionaries

The generator uses 4 default dictionaries to auto-fill instruction files:

### 1. ROLE_DEFAULTS

Defines standard responsibilities and authority for 6 common roles.

**Structure**:
```python
ROLE_DEFAULTS = {
    'RoleName': {
        'primary_responsibilities': [list of strings],
        'secondary_responsibilities': [list of strings],
        'lead_authority': 'description',  # For lead roles
        'support_authority': 'description'  # For support roles
    }
}
```

**Supported Roles**:
- ProductManager (Requirements lead)
- BusinessAnalyst (Requirements support)
- EngineeringManager (Planning lead)
- TechnicalLead (Planning support)
- LeadDeveloper (Implementation lead)
- CodeReviewer (Implementation quality gate)

**Example**:
```python
'EngineeringManager': {
    'primary_responsibilities': [
        'Break down PRD requirements into specific, actionable development tasks',
        'Create comprehensive task breakdown with clear dependencies',
        'Estimate effort and define realistic timeline',
        'Identify project risks and mitigation strategies',
        'Create PROJECT_TASKS.md as primary deliverable',
        'Ensure all PRD requirements are covered by tasks'
    ],
    'secondary_responsibilities': [
        'Ensure tasks are properly scoped for clear progress tracking',
        'Define project milestones and checkpoints',
        'Consider testability requirements for each task',
        'Plan for documentation needs'
    ],
    'lead_authority': 'Final say on task breakdown structure, priorities, milestone definitions, and timeline estimates'
}
```

---

### 2. PHASE_WORKFLOWS

Defines standard workflow phases for Requirements, Planning, and Implementation.

**Structure**:
```python
PHASE_WORKFLOWS = {
    'PhaseName': {
        'phases': [
            {
                'name': 'Sub-phase name',
                'turns': 'turn range',
                'steps': [list of steps],
                'exit_criteria': 'completion criteria'
            }
        ]
    }
}
```

**Planning Phase Example**:
```python
'Planning': {
    'phases': [
        {
            'name': 'PRD Analysis and Component Identification',
            'turns': '1-3',
            'steps': [
                'Review all functional requirements',
                'Identify system components needed',
                'Map requirements to architectural layers'
            ],
            'exit_criteria': 'Complete understanding of all requirements; initial component list identified'
        },
        # ... 2 more phases
    ]
}
```

**Key Insight**: AI models don't need time estimates (no "2-4 hours"), just turn ranges and clear exit criteria.

---

### 3. COLLABORATION_PATTERNS

Defines how role pairs collaborate, make decisions, and divide authority.

**Structure**:
```python
COLLABORATION_PATTERNS = {
    ('LeadRole', 'SupportRole'): {
        'lead_focus': 'what lead focuses on',
        'support_focus': 'what support focuses on',
        'lead_defers_on': 'when lead defers to support',
        'lead_leads_on': 'when lead makes final call',
        'autonomous_lead': [decisions lead can make alone],
        'requires_consensus': [decisions requiring both to agree]
    }
}
```

**EngineeringManager + TechnicalLead Example**:
```python
('EngineeringManager', 'TechnicalLead'): {
    'lead_focus': 'Task breakdown, timeline estimation, project structure, milestone planning',
    'support_focus': 'Architecture design, technology choices, technical feasibility, system design patterns',
    'lead_defers_on': 'Technology stack decisions, architectural patterns, technical dependencies, feasibility concerns',
    'lead_leads_on': 'Task priorities, timeline estimates, milestone definitions, deliverable structure',
    'autonomous_lead': [
        'Task breakdown structure and granularity',
        'Task priority ordering',
        'Milestone definitions and checkpoints',
        'PROJECT_TASKS.md format and organization',
        'Effort estimates for individual tasks'
    ],
    'requires_consensus': [
        'Overall architectural approach',
        'Technology stack choices',
        'Technical dependencies between tasks',
        'Feasibility of timeline',
        'Risk assessment and mitigation strategies',
        'Final approval before signaling [[PROJECT_COMPLETE]]'
    ]
}
```

---

### 4. DEFINITION_OF_DONE

Defines phase-specific completion criteria and signal conditions.

**Structure**:
```python
DEFINITION_OF_DONE = {
    'PhaseName': {
        'phase_complete_criteria': [list of completion criteria],
        'signal_conditions': [list of conditions for signaling completion]
    }
}
```

**Planning Phase Example**:
```python
'Planning': {
    'phase_complete_criteria': [
        'PROJECT_TASKS.md exists with comprehensive task breakdown',
        'ARCHITECTURE.md addresses all PRD requirements',
        'All functional and non-functional requirements are covered by tasks',
        'Task dependencies are clearly identified',
        'Critical path is identified and documented',
        'Risks are documented with mitigation strategies',
        '{other_role} has reviewed and approved',
        'Both team members signal [[PROJECT_COMPLETE]]'
    ],
    'signal_conditions': [
        'All planning deliverables are complete (PROJECT_TASKS.md, ARCHITECTURE.md)',
        '{other_role} confirms technical feasibility and timeline',
        'No blocking questions or concerns remain',
        'Implementation team can work from this plan'
    ]
}
```

**Template Substitution**:
- `{other_role}` is replaced with the teammate's role name (e.g., "TechnicalLead")
- Generates checklist format for completion criteria
- Generates numbered list for signal conditions

**Generated Output**:
```markdown
## Definition of Done

This planning phase is complete when:
- [ ] PROJECT_TASKS.md exists with comprehensive task breakdown
- [ ] ARCHITECTURE.md addresses all PRD requirements
- [ ] All functional and non-functional requirements are covered by tasks
- [ ] Task dependencies are clearly identified
- [ ] Critical path is identified and documented
- [ ] Risks are documented with mitigation strategies
- [ ] TechnicalLead has reviewed and approved
- [ ] Both team members signal [[PROJECT_COMPLETE]]

**You may signal [[PROJECT_COMPLETE]] when:**
1. All planning deliverables are complete (PROJECT_TASKS.md, ARCHITECTURE.md)
2. TechnicalLead confirms technical feasibility and timeline
3. No blocking questions or concerns remain
4. Implementation team can work from this plan
```

---

## Automation Levels

### What Is Automated (Category 5+ TODOs)

✅ **Primary Responsibilities** - Role-based defaults
✅ **Secondary Responsibilities** - Role-based defaults
✅ **Decision Authority** - Auto-assigned based on lead/support role
✅ **Workflow Phases** - Phase-based standard workflows (3-4 sub-phases each)
✅ **Collaboration Protocols** - Role-pair patterns define focus areas
✅ **Decision Making** - Autonomous vs consensus boundaries from patterns
✅ **Exit Criteria** - Phase-based standard exit criteria
✅ **Definition of Done** - Phase-specific completion criteria and signal conditions (NEW in v2.1!)
✅ **Input/Output Artifacts** - Filled during Stage 2 refinement from PRD
✅ **FR/NFR Counts** - Extracted from PRD and injected into templates

### What Remains Manual (Category 1-4 TODOs)

❌ **Domain Guidance** - Highly specialized (Financial, Healthcare, Gaming, etc.)
❌ **Technology Guidance** - Tech stack specific (Python, React, Go, etc.)
❌ **Common Pitfalls** - Project-type specific (optional section)

**Current Manual Workload**: ~2-3 sections per file (down from ~15 TODOs)

**Reduction**: **~93% automation** (14 out of 15 TODOs now auto-filled)

---

## Testing & Refinement

### Stage 1: Initial Generation

**Command**:
```bash
python scripts/generate_instruction_files.py
```

**Interview Questions**:
- Project name, path, type, domain, tech stack
- Number of phases (2 or 3)
- Roles for each phase

**Output**:
- Instruction files with defaults filled in
- Only Domain + Tech guidance TODOs remain
- README.md, SESSION_MAPPING.md, USER_REQUEST.md templates
- project_config.json for future reference

**Testing Focus**:
- Are responsibilities appropriate for the role?
- Are workflows complete for the phase?
- Are collaboration patterns correct for the role pair?

---

### Stage 2: Phase 2 Refinement

**Command**:
```bash
python scripts/generate_instruction_files.py \
  --refine \
  --phase 2 \
  --prd-file /path/to/PRD.md \
  --project-dir /path/to/project
```

**What It Does**:
1. Reads PRD.md and extracts:
   - Functional requirements (FR-1, FR-2, etc.)
   - Non-functional requirements (NFR-1, NFR-2, etc.)
   - Data model references
   - Success criteria
2. Finds Phase 2 instruction files (ROLE_*_Planning.md)
3. Auto-fills:
   - Input Artifacts: `- PRD.md`
   - Output Artifacts: `- ARCHITECTURE.md`, `- PROJECT_TASKS.md`, etc.
   - Success Criteria: Based on PRD requirements
   - Workflow steps: Injects FR count ("Review FR-1 through FR-4")

**PRD Parsing Requirements**:

The script expects PRD format:
```markdown
### 5.1 Add Expense Feature (FR-1)
**Requirement ID:** FR-1
**Description:** Users must be able to...
```

**Regex Pattern**:
```python
fr_pattern = r'\*\*Requirement\s+ID:\*\*\s+(FR-\d+)\s*\n\*\*Description:\*\*\s+(.+?)(?=\n\*\*(?:Input|Data|Success)|###|$)'
```

**Testing Focus**:
- Does script extract correct FR/NFR count?
- Are Input/Output artifacts properly formatted (no double-dash bug)?
- Is FR range correct in workflow steps?

---

### Known Issues & Fixes

#### Issue 1: Double-Dash in Artifacts (FIXED)

**Problem**:
```markdown
**Input Artifacts:**
- - PRD.md    # Wrong!
```

**Root Cause**: Template already has `- ` prefix, script was adding another one.

**Fix** (Line 1020):
```python
# Before
input_list = '\n'.join(f"- {artifact}" for artifact in prd_data['input_artifacts'])

# After
input_list = '\n- '.join(artifact for artifact in prd_data['input_artifacts'])
```

#### Issue 2: Incorrect FR Count (FIXED)

**Problem**: Showed "FR-1 through FR-0" when no FRs extracted

**Root Cause**: Regex didn't match PRD format

**Fix** (Lines 914, 924):
```python
# Updated regex to match "**Requirement ID:** FR-1 \n **Description:**" format
fr_pattern = r'\*\*Requirement\s+ID:\*\*\s+(FR-\d+)\s*\n\*\*Description:\*\*\s+(.+?)...'
```

**Fix** (Lines 1061-1062):
```python
# Dynamic FR range based on actual count
fr_count = len(prd_data['functional_requirements'])
fr_range = f'FR-1 through FR-{fr_count}' if fr_count > 0 else 'all functional requirements'
```

---

## Future Enhancements

### 1. Template Library for Domain/Tech Guidance

**Problem**: Domain and Tech guidance still require manual authoring

**Solution**: Create reusable template library

**Structure**:
```
templates/
├── domain_guidance/
│   ├── financial.md         # Decimal precision, audit trails
│   ├── healthcare.md        # HIPAA, PHI handling
│   ├── gaming.md            # Frame rates, collision detection
│   └── general.md           # Default fallback
└── tech_guidance/
    ├── python_cli.md        # Click/argparse examples
    ├── python_react.md      # FastAPI + React patterns
    ├── javascript_node.md   # Express patterns
    └── general.md           # Default fallback
```

**Implementation**:
```python
def _load_domain_guidance(domain: str) -> str:
    """Load domain-specific guidance from template library"""
    guidance_file = self.templates_dir / f"domain_guidance/{domain}.md"
    if guidance_file.exists():
        return guidance_file.read_text()
    return "<!-- TODO: Add domain-specific guidance -->"
```

**Benefit**: Further reduce manual TODO completion from 2-3 sections to 0-1

---

### 2. Stage 3: Phase 3 Refinement

**Purpose**: Auto-fill Phase 3 (Implementation) templates using ARCHITECTURE.md and PROJECT_TASKS.md

**Command**:
```bash
python scripts/generate_instruction_files.py \
  --refine \
  --phase 3 \
  --architecture-file ARCHITECTURE.md \
  --tasks-file PROJECT_TASKS.md \
  --project-dir /path/to/project
```

**What It Would Fill**:
- Technology stack from ARCHITECTURE.md
- Project structure recommendations
- Key implementation patterns
- Task list reference for LeadDeveloper

**Status**: Planned, not yet implemented

---

### 3. Common Pitfalls Library

**Problem**: "Common Pitfalls" section is currently TODO

**Solution**: Create role+project-type specific pitfall templates

**Structure**:
```
templates/pitfalls/
├── EngineeringManager_cli.md      # Task scoping for CLI projects
├── EngineeringManager_webapp.md   # Task scoping for web projects
├── TechnicalLead_cli.md           # Architecture pitfalls for CLI
└── LeadDeveloper_python.md        # Python-specific code pitfalls
```

**Benefit**: Provide actionable guidance without manual authoring

---

### 4. Interactive TODO Completion

**Concept**: Prompt user for remaining TODOs during generation

**Example**:
```
Domain Guidance for Financial projects:
  What currency precision is required? [Decimal with 2 places]
  Are audit trails needed? [Y/n]
  ...
```

**Benefit**: Collect project-specific details upfront, further reduce post-generation work

---

## Change Log

### 2025-11-14: Version 2.1 - Definition of Done Defaults

**Added**:
- DEFINITION_OF_DONE dictionary for Requirements/Planning/Implementation phases
- `_build_definition_of_done()` method to generate completion criteria
- Auto-fill phase-specific completion criteria and signal conditions
- Teammate name substitution in completion criteria

**Result**: Reduced TODOs from ~5 to ~3 per file (~93% automation total)

**Impact**: Definition of Done section now fully automated, eliminating 2 TODOs per file

---

### 2025-11-14: Version 2.0 - Defaults-Based Generation

**Added**:
- ROLE_DEFAULTS dictionary with 6 common roles
- PHASE_WORKFLOWS dictionary for Requirements/Planning/Implementation
- COLLABORATION_PATTERNS for 3 common role pairs
- Updated `_get_role_template()` to use defaults
- Auto-fill responsibilities, authority, workflows, collaboration protocols

**Fixed**:
- Double-dash bug in artifact formatting
- FR count extraction from PRD
- Incorrect FR range display ("FR-0" → "FR-4")

**Result**: Reduced TODOs from ~15 to ~5 per file (~67% automation)

**Testing**: Expense Tracker CLI (Financial domain, Python, 3-phase workflow)

---

### 2025-11-13: Version 1.0 - Initial Release

**Features**:
- Interactive interview-based generation
- Stage 2 PRD-based refinement
- Template variables for customization
- Support for 2-phase and 3-phase workflows

**Limitations**:
- ~15 TODOs per generated file
- Manual effort required for most sections
- No role/phase defaults

---

## Best Practices

### When to Use Initial Generation

✅ Starting a new project from scratch
✅ Need all 3 phases (Requirements → Planning → Implementation)
✅ Want standard role assignments

❌ Adding single role to existing project
❌ Using non-standard roles
❌ Need heavy customization beyond domain/tech

### When to Use Refinement Mode

✅ PRD exists and you want to generate Planning templates
✅ Want to auto-fill artifacts and success criteria
✅ PRD follows standard format with FR-1, NFR-1 markers

❌ PRD uses non-standard format
❌ No PRD yet (use initial generation first)

### Customization Points

**Always Customize**:
1. Domain Guidance (Financial, Healthcare, Gaming, etc.)
2. Technology Guidance (Python, React, specific frameworks)

**Sometimes Customize**:
3. Common Pitfalls (if project has unique risks)
4. Workflow phases (if non-standard process needed)

**Rarely Customize**:
5. Responsibilities (defaults work for 99% of cases)
6. Collaboration patterns (role pairs are well-defined)

---

## Troubleshooting

### Problem: Script extracts 0 functional requirements

**Symptoms**:
```
Extracted 0 functional requirements
Extracted 0 non-functional requirements
```

**Cause**: PRD format doesn't match expected pattern

**Solution**: Ensure PRD uses this format:
```markdown
**Requirement ID:** FR-1
**Description:** Description here
```

**Check**: Run test regex:
```bash
grep -A1 "Requirement ID" PRD.md
```

---

### Problem: Generated files have double-dash in artifacts

**Symptoms**:
```markdown
- - PRD.md
- - ARCHITECTURE.md
```

**Cause**: Using old version of script (pre-fix)

**Solution**: Update to latest version with artifact formatting fix (Line 1020)

---

### Problem: Workflow shows "FR-1 through FR-0"

**Cause**: FR extraction failed (regex mismatch)

**Solution**:
1. Check PRD format matches expected pattern
2. Verify script has updated FR extraction regex (Lines 914, 924)
3. Check FR count logic (Lines 1061-1062)

---

## Related Documentation

- `instruction_file_creation_guide.md` - Overall methodology
- `instruction_file_templates.md` - Template structure and variables
- `instruction_file_USER_REQUEST_Guidelines.md` - How to write good USER_REQUEST.md
- `role_authority_patterns.md` - Decision-making framework
- `instruction_file_examples.md` - Complete example files

---

## Contact & Feedback

For issues, improvements, or questions about the instruction generator:
- Review this documentation first
- Check existing examples in `templates/projects/`
- Test with simple project before complex one
- Document any new patterns discovered for future updates
