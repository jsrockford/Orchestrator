# Documentation Hub

This directory hosts the layered documentation set described in `docs/Documentation_Guidelines.md`. Use the map below to jump to the right audience-specific guide.

| Audience | Start Here | Highlights |
| --- | --- | --- |
| Engineers & stakeholders | [`architecture.md`](architecture.md) | End-to-end system overview, data flow, and component responsibilities. |
| Backend developers | [`backend/development_guide.md`](backend/development_guide.md) | Environment setup, orchestrator modules, testing strategy, and config tips. |
| Backend API consumers | [`backend/api_reference.md`](backend/api_reference.md) | FastAPI surface exposed to the React UI and external automation. |
| Client builders / tooling | [`openapi.json`](openapi.json) | Machine-readable schema (`scripts/generate_openapi.py`) for SDK generation and contract tests. |
| Frontend developers | [`frontend/development_guide.md`](frontend/development_guide.md) | React/Vite project structure, state flows, and UI conventions. |
| Operators / DevOps | [`deployment.md`](deployment.md) | How to start/stop services, manage tmux sessions, and monitor logs. |
| New AI sessions | [`onboarding.md`](onboarding.md) | Quick-start checklist covering doc order, startup scripts, and collaboration rules. |
| **Instruction File Creators** | [`instruction_file_creation_guide.md`](instruction_file_creation_guide.md) | **NEW:** Complete guide to creating AI instruction files for multi-session orchestration workflows. |

## Instruction File Creation System (NEW)

The Orchestrator now includes a comprehensive system for creating custom AI instruction files for any project type. This enables multi-AI collaborative workflows with specialized roles.

**Quick Start:**
1. **Read the methodology:** [`instruction_file_creation_guide.md`](instruction_file_creation_guide.md) - Core concepts and step-by-step process
2. **Use the generator:** Run `python scripts/generate_instruction_files.py` - Interactive tool that creates files for you
3. **Customize templates:** [`instruction_file_templates.md`](instruction_file_templates.md) - Ready-to-use templates with variables
4. **Learn from examples:** [`instruction_file_examples.md`](instruction_file_examples.md) - Complete examples for different project types
5. **Understand authority:** [`role_authority_patterns.md`](role_authority_patterns.md) - Decision-making and collaboration patterns

**What You Can Create:**
- Multi-phase workflows (Requirements → Planning → Implementation)
- Specialized AI roles (Product Manager, Developer, Reviewer, etc.)
- Domain-specific guidance (Financial, Gaming, Web Development, Data Processing)
- Quality-focused collaboration patterns

**Documentation Map:**

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [`instruction_file_creation_guide.md`](instruction_file_creation_guide.md) | Complete methodology and concepts | First read - learn the system |
| [`instruction_file_generator.md`](instruction_file_generator.md) | Script usage and customization | Generate files for new project |
| [`instruction_file_templates.md`](instruction_file_templates.md) | Variable-based templates | Reference when customizing |
| [`instruction_file_examples.md`](instruction_file_examples.md) | Complete working examples | See domain-specific patterns |
| [`role_authority_patterns.md`](role_authority_patterns.md) | Decision-making patterns | Define role collaboration |

**Existing Examples:**
- Terminal Applications: `templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/`
- Web UI Enhancements: `templates/hold/CLAUDE_EXAMPLES/PROJECT_INSTRUCTIONS_POC/WEBDEVFILES/`

---

Each guide references real modules (e.g., `src/orchestrator/orchestrator.py`) and keeps success-path plus failure-path instructions close at hand. Update these docs whenever code paths change so a new contributor can reproduce your steps within 15 minutes without extra context.
