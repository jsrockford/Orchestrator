#!/usr/bin/env python3
"""
Interactive Instruction File Generator for Orchestrator

This script interviews the user about their project and automatically generates
appropriate instruction files for a multi-session AI orchestration workflow.

Usage:
    python scripts/generate_instruction_files.py

The script will:
1. Ask questions about your project
2. Determine appropriate phases and roles
3. Generate customized instruction files
4. Create supporting documentation (README.md, SESSION_MAPPING.md)

Author: Orchestrator Development Team
Version: 1.0
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json


@dataclass
class ProjectConfig:
    """Configuration for the project being created"""
    project_name: str
    project_path: str
    project_type: str  # cli, webapp, game, library, etc.
    domain: str  # financial, gaming, general, etc.
    tech_stack: str  # python, javascript, etc.
    num_phases: int = 3
    roles: Dict[int, List[str]] = field(default_factory=dict)
    description: str = ""
    existing_code: bool = False
    existing_code_path: str = ""


class InstructionFileGenerator:
    """Generates instruction files based on project configuration"""

    def __init__(self):
        self.repo_root = Path(__file__).parent.parent
        self.templates_dir = self.repo_root / "templates"
        self.template_file = self.templates_dir / "ALL_MODELS_TEMPLATE.md"

    def run(self):
        """Main entry point for the generator"""
        print("=" * 70)
        print("Orchestrator Instruction File Generator")
        print("=" * 70)
        print()
        print("This wizard will help you create instruction files for your project.")
        print("Answer the questions below to generate a customized multi-AI workflow.")
        print()

        # Gather project information
        config = self._interview_user()

        # Confirm configuration
        if not self._confirm_configuration(config):
            print("\nConfiguration cancelled. Exiting.")
            return

        # Generate files
        print("\nGenerating instruction files...")
        output_dir = self._generate_instruction_files(config)

        # Show completion message
        self._show_completion_message(config, output_dir)

    def _interview_user(self) -> ProjectConfig:
        """Interview the user to gather project details"""
        print("STEP 1: PROJECT BASICS")
        print("-" * 70)

        # Project name
        project_name = self._prompt(
            "What is your project name?",
            default="My Project"
        )

        # Project path
        default_path = f"/home/{os.getenv('USER')}/Projects/{project_name.replace(' ', '_')}"
        project_path = self._prompt(
            "What is the absolute path where this project will be developed?",
            default=default_path
        )

        # Project type
        print("\nWhat type of project is this?")
        print("  1. CLI/Terminal Application")
        print("  2. Web Application (full-stack)")
        print("  3. Web UI for Existing Application")
        print("  4. Game")
        print("  5. Library/Package")
        print("  6. API/Service")
        print("  7. Data Processing/Analysis")
        print("  8. Other")

        project_type_map = {
            "1": "cli",
            "2": "webapp",
            "3": "webui-addon",
            "4": "game",
            "5": "library",
            "6": "api",
            "7": "data",
            "8": "other"
        }

        project_type_choice = self._prompt("Select option (1-8)", default="1")
        project_type = project_type_map.get(project_type_choice, "cli")

        # Domain
        print("\nWhat domain/industry is this project in?")
        print("  1. Financial/Accounting")
        print("  2. Gaming")
        print("  3. Healthcare")
        print("  4. E-commerce")
        print("  5. Education")
        print("  6. General/Other")

        domain_map = {
            "1": "financial",
            "2": "gaming",
            "3": "healthcare",
            "4": "ecommerce",
            "5": "education",
            "6": "general"
        }

        domain_choice = self._prompt("Select option (1-6)", default="6")
        domain = domain_map.get(domain_choice, "general")

        # Tech stack
        print("\nWhat is your primary technology stack?")
        print("  1. Python")
        print("  2. JavaScript/Node.js")
        print("  3. Python + React")
        print("  4. Python + Vue")
        print("  5. Other")

        tech_stack_map = {
            "1": "python",
            "2": "javascript",
            "3": "python-react",
            "4": "python-vue",
            "5": "other"
        }

        tech_choice = self._prompt("Select option (1-5)", default="1")
        tech_stack = tech_stack_map.get(tech_choice, "python")

        # Project description
        description = self._prompt(
            "\nBriefly describe what this project does (1-2 sentences)",
            default="A software application"
        )

        # Existing code
        print()
        existing_code = self._prompt_yes_no(
            "Are you adding to or enhancing existing code?",
            default=False
        )

        existing_code_path = ""
        if existing_code:
            existing_code_path = self._prompt(
                "What is the path to the existing code file(s)?",
                default=""
            )

        # Create initial config
        config = ProjectConfig(
            project_name=project_name,
            project_path=project_path,
            project_type=project_type,
            domain=domain,
            tech_stack=tech_stack,
            description=description,
            existing_code=existing_code,
            existing_code_path=existing_code_path
        )

        # Determine phases
        print()
        print("STEP 2: WORKFLOW PHASES")
        print("-" * 70)

        num_phases = self._determine_phases(config)
        config.num_phases = num_phases

        # Determine roles for each phase
        print()
        print("STEP 3: ROLE SELECTION")
        print("-" * 70)

        config.roles = self._select_roles(config)

        return config

    def _determine_phases(self, config: ProjectConfig) -> int:
        """Determine how many phases are needed"""
        # Simple projects can skip PRD
        if config.project_type == "cli" and not config.existing_code:
            print("\nFor simple CLI tools, you can use a 2-phase workflow:")
            print("  - Phase 1: Planning (skip PRD)")
            print("  - Phase 2: Implementation")
            print()
            use_2_phase = self._prompt_yes_no(
                "Use simplified 2-phase workflow?",
                default=False
            )
            if use_2_phase:
                return 2

        # Enhancement projects might skip PRD
        if config.existing_code:
            print("\nFor enhancement projects, you can use a 2-phase workflow:")
            print("  - Phase 1: Planning")
            print("  - Phase 2: Implementation")
            print()
            use_2_phase = self._prompt_yes_no(
                "Use simplified 2-phase workflow?",
                default=True
            )
            if use_2_phase:
                return 2

        # Default is 3 phases
        print("\nUsing standard 3-phase workflow:")
        print("  - Phase 1: Requirements (PRD)")
        print("  - Phase 2: Planning (Task Breakdown)")
        print("  - Phase 3: Implementation")
        print()

        return 3

    def _select_roles(self, config: ProjectConfig) -> Dict[int, List[str]]:
        """Select roles for each phase"""
        roles = {}

        if config.num_phases == 2:
            # 2-phase workflow (Planning + Implementation)
            roles = self._select_roles_2_phase(config)
        else:
            # Standard 3-phase workflow
            roles = self._select_roles_3_phase(config)

        return roles

    def _select_roles_2_phase(self, config: ProjectConfig) -> Dict[int, List[str]]:
        """Select roles for 2-phase workflow"""
        roles = {}

        # Phase 1: Planning
        print("\nPHASE 1: Planning")
        print("Select roles for planning phase (2-4 recommended):")
        print("  1. Engineering Manager (recommended, lead)")
        print("  2. Technical Lead (recommended)")
        print("  3. Full Stack Architect")
        print("  4. Security Architect")

        phase1_choices = self._prompt(
            "Enter numbers separated by commas (e.g., 1,2)",
            default="1,2"
        ).split(",")

        role_map = {
            "1": "EngineeringManager",
            "2": "TechnicalLead",
            "3": "FullStackArchitect",
            "4": "SecurityArchitect"
        }

        roles[1] = [role_map[c.strip()] for c in phase1_choices if c.strip() in role_map]

        # Phase 2: Implementation
        print("\nPHASE 2: Implementation")
        print("Select roles for implementation phase (2-4 recommended):")
        print("  1. Lead Developer (recommended, lead)")
        print("  2. Code Reviewer (highly recommended)")
        print("  3. QA Engineer")
        print("  4. Security Reviewer")

        phase2_choices = self._prompt(
            "Enter numbers separated by commas (e.g., 1,2)",
            default="1,2"
        ).split(",")

        role_map = {
            "1": "LeadDeveloper",
            "2": "CodeReviewer",
            "3": "QAEngineer",
            "4": "SecurityReviewer"
        }

        roles[2] = [role_map[c.strip()] for c in phase2_choices if c.strip() in role_map]

        return roles

    def _select_roles_3_phase(self, config: ProjectConfig) -> Dict[int, List[str]]:
        """Select roles for 3-phase workflow"""
        roles = {}

        # Phase 1: Requirements
        print("\nPHASE 1: Requirements")
        print("Select roles for requirements phase (2-3 recommended):")
        print("  1. Product Manager (recommended, lead)")
        print("  2. Business Analyst (recommended)")
        print("  3. UX Designer")
        print("  4. Security Analyst")

        if config.domain != "general":
            print(f"  5. {config.domain.title()} Domain Expert")

        phase1_choices = self._prompt(
            "Enter numbers separated by commas (e.g., 1,2)",
            default="1,2"
        ).split(",")

        role_map = {
            "1": "ProductManager",
            "2": "BusinessAnalyst",
            "3": "UXDesigner",
            "4": "SecurityAnalyst",
            "5": f"{config.domain.title()}Expert"
        }

        roles[1] = [role_map[c.strip()] for c in phase1_choices if c.strip() in role_map]

        # Phase 2: Planning
        print("\nPHASE 2: Planning")
        print("Select roles for planning phase (2-3 recommended):")
        print("  1. Engineering Manager (recommended, lead)")
        print("  2. Technical Lead (recommended)")
        print("  3. Full Stack Architect")
        print("  4. Security Architect")

        phase2_choices = self._prompt(
            "Enter numbers separated by commas (e.g., 1,2)",
            default="1,2"
        ).split(",")

        role_map = {
            "1": "EngineeringManager",
            "2": "TechnicalLead",
            "3": "FullStackArchitect",
            "4": "SecurityArchitect"
        }

        roles[2] = [role_map[c.strip()] for c in phase2_choices if c.strip() in role_map]

        # Phase 3: Implementation
        print("\nPHASE 3: Implementation")
        print("Select roles for implementation phase (2-4 recommended):")
        print("  1. Lead Developer (recommended, lead)")
        print("  2. Code Reviewer (highly recommended)")
        print("  3. QA Engineer")
        print("  4. Security Reviewer")
        print("  5. Performance Engineer")

        phase3_choices = self._prompt(
            "Enter numbers separated by commas (e.g., 1,2)",
            default="1,2"
        ).split(",")

        role_map = {
            "1": "LeadDeveloper",
            "2": "CodeReviewer",
            "3": "QAEngineer",
            "4": "SecurityReviewer",
            "5": "PerformanceEngineer"
        }

        roles[3] = [role_map[c.strip()] for c in phase3_choices if c.strip() in role_map]

        return roles

    def _confirm_configuration(self, config: ProjectConfig) -> bool:
        """Show configuration and get confirmation"""
        print()
        print("=" * 70)
        print("CONFIGURATION SUMMARY")
        print("=" * 70)
        print(f"Project Name: {config.project_name}")
        print(f"Project Path: {config.project_path}")
        print(f"Project Type: {config.project_type}")
        print(f"Domain: {config.domain}")
        print(f"Tech Stack: {config.tech_stack}")
        print(f"Description: {config.description}")
        print(f"Number of Phases: {config.num_phases}")
        print()

        for phase_num, phase_roles in config.roles.items():
            phase_name = self._get_phase_name(phase_num, config.num_phases)
            print(f"Phase {phase_num} ({phase_name}):")
            for role in phase_roles:
                print(f"  - {role}")
        print()

        total_files = sum(len(roles) for roles in config.roles.values())
        print(f"This will generate {total_files} instruction files plus documentation.")
        print()

        return self._prompt_yes_no("Proceed with generation?", default=True)

    def _generate_instruction_files(self, config: ProjectConfig) -> Path:
        """Generate all instruction files and documentation"""
        # Create output directory
        output_dir = self.templates_dir / f"projects/{config.project_name.replace(' ', '_')}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load base template
        with open(self.template_file, 'r') as f:
            base_template = f.read()

        # Generate instruction files for each phase
        for phase_num, phase_roles in config.roles.items():
            phase_name = self._get_phase_name(phase_num, config.num_phases)

            for role_name in phase_roles:
                self._generate_role_file(
                    config, phase_num, phase_name, role_name,
                    base_template, output_dir
                )

        # Generate supporting documentation
        self._generate_readme(config, output_dir)
        self._generate_session_mapping(config, output_dir)
        self._generate_user_request_template(config, output_dir)

        # Save configuration
        self._save_config(config, output_dir)

        return output_dir

    def _generate_role_file(
        self,
        config: ProjectConfig,
        phase_num: int,
        phase_name: str,
        role_name: str,
        base_template: str,
        output_dir: Path
    ):
        """Generate a single role instruction file"""
        # Determine if this is the lead role (first in list)
        is_lead = config.roles[phase_num][0] == role_name

        # Get other roles in this phase
        other_roles = [r for r in config.roles[phase_num] if r != role_name]
        other_role_name = other_roles[0] if other_roles else "teammate"

        # Create filename
        filename = f"ROLE_{role_name}_{phase_name}.md"
        filepath = output_dir / filename

        # Get role template content
        role_content = self._get_role_template(
            config, phase_num, phase_name, role_name,
            is_lead, other_role_name
        )

        # Combine base template + role content
        full_content = self._customize_template(
            base_template + "\n" + role_content,
            config,
            phase_name,
            role_name,
            other_role_name
        )

        # Write file
        with open(filepath, 'w') as f:
            f.write(full_content)

        print(f"  Created: {filename}")

    def _get_role_template(
        self,
        config: ProjectConfig,
        phase_num: int,
        phase_name: str,
        role_name: str,
        is_lead: bool,
        other_role_name: str
    ) -> str:
        """Get template content for a specific role"""
        # This is a simplified version - in production, you'd have
        # complete templates for each role type stored separately

        lead_marker = "**LEAD ROLE** - " if is_lead else ""

        return f"""
## Your Role: {role_name} ({phase_name} Phase)

**Primary Responsibilities:**
- [TODO: Customize for {role_name} role]
- [Add specific responsibilities]
- [Add deliverables]

**Secondary Responsibilities:**
- [TODO: Add supporting activities]

**Team Position:**
- Reports to: Project Stakeholder
- Collaborates with: {other_role_name}
- Decision Authority: {lead_marker}[TODO: Define authority level]

## Project Context

**Phase**: {phase_name}
**Working Directory:** {config.project_path}

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

## {config.domain.title()} Domain Guidance

<!-- TODO: Add domain-specific guidance for {config.domain} projects -->

## {config.tech_stack.title()} Technology Guidance

<!-- TODO: Add technology-specific patterns and examples -->

## Collaboration Protocols

**With {other_role_name}:**
- They focus on: [TODO: Define their focus]
- You focus on: [TODO: Define your focus]
- Defer to them on: [TODO: When to follow their lead]
- Lead on: [TODO: When you have final say]

**Decision Making:**
- You can decide autonomously: [TODO: List autonomous decisions]
- Requires {other_role_name} consensus: [TODO: List collaborative decisions]

## Common Pitfalls to Avoid

**[Category]:**
- ⚠️ Don't [TODO: Add anti-patterns]
- ✅ Do [TODO: Add best practices]

## Definition of Done

This {phase_name.lower()} phase is complete when:
- [ ] [TODO: Add specific completion criteria]
- [ ] {other_role_name} has reviewed and approved
- [ ] Both team members signal [[PROJECT_COMPLETE]]

**You may signal [[PROJECT_COMPLETE]] when:**
1. [TODO: Add condition]
2. {other_role_name} confirms agreement
3. All deliverables are complete
"""

    def _customize_template(
        self,
        template: str,
        config: ProjectConfig,
        phase_name: str,
        role_name: str,
        other_role_name: str
    ) -> str:
        """Replace variables in template with actual values"""
        replacements = {
            "[PROJECT_PATH]": config.project_path,
            "[PROJECT_NAME]": config.project_name,
            "[ROLE_NAME]": role_name,
            "[PHASE_NAME]": phase_name,
            "[OTHER_ROLE_NAME]": other_role_name,
            "[DOMAIN]": config.domain,
            "[TECH_STACK]": config.tech_stack,
        }

        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result

    def _generate_readme(self, config: ProjectConfig, output_dir: Path):
        """Generate README.md with workflow overview"""
        content = f"""# {config.project_name} - Orchestrator Instruction Files

**Generated**: {self._get_timestamp()}
**Project Type**: {config.project_type}
**Domain**: {config.domain}
**Tech Stack**: {config.tech_stack}

## Project Description

{config.description}

## Workflow Overview

This project uses a {config.num_phases}-phase orchestrated AI workflow:

"""

        for phase_num, phase_roles in config.roles.items():
            phase_name = self._get_phase_name(phase_num, config.num_phases)
            content += f"### Phase {phase_num}: {phase_name}\n\n"
            content += f"**Roles:**\n"
            for role in phase_roles:
                is_lead = role == phase_roles[0]
                lead_marker = " (Lead)" if is_lead else ""
                content += f"- {role}{lead_marker}\n"
            content += "\n"

        content += """
## Usage

See `SESSION_MAPPING.md` for detailed instructions on running each phase.

## Customization Needed

The generated instruction files contain TODO markers where you need to add:
- Domain-specific guidance
- Technology-specific examples
- Detailed workflow phases
- Common pitfalls for your project type

Search for `TODO:` in each file and customize accordingly.

## Next Steps

1. Review all generated instruction files
2. Complete TODO sections with project-specific content
3. Test with a simple example scenario
4. Iterate and refine based on results
"""

        with open(output_dir / "README.md", 'w') as f:
            f.write(content)

        print(f"  Created: README.md")

    def _generate_session_mapping(self, config: ProjectConfig, output_dir: Path):
        """Generate SESSION_MAPPING.md with usage instructions"""
        content = f"""# Session Mapping Guide - {config.project_name}

This document explains which instruction files to use for each orchestration session.

---

"""

        for phase_num, phase_roles in config.roles.items():
            phase_name = self._get_phase_name(phase_num, config.num_phases)
            content += f"""## Phase {phase_num}: {phase_name}

**Roles:**
"""
            for i, role in enumerate(phase_roles):
                is_lead = i == 0
                lead_marker = " (Lead)" if is_lead else ""
                content += f"- AI {i+1}: `ROLE_{role}_{phase_name}.md`{lead_marker}\n"

            content += f"""
**Command Example:**
```bash
python run_orchestrated_discussion.py \\
"""
            for i, role in enumerate(phase_roles):
                content += f"  --ai{i+1}-instruction-file templates/projects/{config.project_name.replace(' ', '_')}/ROLE_{role}_{phase_name}.md \\\n"

            content += f"""  --group-system-prompt "[TODO: Add phase-specific prompt]" \\
  --max-turns 10 \\
  --log-file artifacts/phase{phase_num}/conversation.log
```

---

"""

        with open(output_dir / "SESSION_MAPPING.md", 'w') as f:
            f.write(content)

        print(f"  Created: SESSION_MAPPING.md")

    def _generate_user_request_template(self, config: ProjectConfig, output_dir: Path):
        """Generate USER_REQUEST.md template"""
        content = f"""# User Request - {config.project_name}

## Problem Statement

[Describe the problem you're trying to solve]

## What I Need

[Describe what you want the software to do]

## Example Use Case

[Provide a concrete example of how this would be used]

## Inputs

[What information/data will users provide?]

## Expected Outputs

[What should the system produce?]

## Important Considerations

[Any constraints, preferences, or special requirements]
"""

        with open(output_dir / "USER_REQUEST.md", 'w') as f:
            f.write(content)

        print(f"  Created: USER_REQUEST.md (template)")

    def _save_config(self, config: ProjectConfig, output_dir: Path):
        """Save configuration to JSON for reference"""
        config_dict = {
            "project_name": config.project_name,
            "project_path": config.project_path,
            "project_type": config.project_type,
            "domain": config.domain,
            "tech_stack": config.tech_stack,
            "num_phases": config.num_phases,
            "roles": config.roles,
            "description": config.description,
            "existing_code": config.existing_code,
            "existing_code_path": config.existing_code_path
        }

        with open(output_dir / "project_config.json", 'w') as f:
            json.dump(config_dict, f, indent=2)

        print(f"  Created: project_config.json")

    def _show_completion_message(self, config: ProjectConfig, output_dir: Path):
        """Display completion message with next steps"""
        print()
        print("=" * 70)
        print("GENERATION COMPLETE!")
        print("=" * 70)
        print()
        print(f"Instruction files created in: {output_dir}")
        print()
        print("Next Steps:")
        print("1. Review all generated files")
        print("2. Complete TODO sections in each instruction file:")
        print("   - Add domain-specific guidance")
        print("   - Add technology-specific examples")
        print("   - Define detailed workflow phases")
        print("   - Add common pitfalls for your context")
        print()
        print("3. Create your USER_REQUEST.md with project requirements")
        print()
        print("4. Test the workflow:")
        print(f"   - See {output_dir}/SESSION_MAPPING.md for usage instructions")
        print()
        print("5. Iterate and refine based on results")
        print()
        print("For detailed guidance, see:")
        print("  - docs/instruction_file_creation_guide.md")
        print("  - docs/instruction_file_templates.md")
        print()

    # Utility methods
    def _prompt(self, question: str, default: str = "") -> str:
        """Prompt user for input with optional default"""
        if default:
            question += f" [{default}]"
        question += ": "

        response = input(question).strip()
        return response if response else default

    def _prompt_yes_no(self, question: str, default: bool = True) -> bool:
        """Prompt for yes/no answer"""
        default_str = "Y/n" if default else "y/N"
        response = input(f"{question} [{default_str}]: ").strip().lower()

        if not response:
            return default

        return response in ['y', 'yes']

    def _get_phase_name(self, phase_num: int, total_phases: int) -> str:
        """Get phase name based on phase number and total phases"""
        if total_phases == 2:
            return ["Planning", "Implementation"][phase_num - 1]
        else:  # 3 phases
            return ["Requirements", "Planning", "Implementation"][phase_num - 1]

    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    """Main entry point"""
    try:
        generator = InstructionFileGenerator()
        generator.run()
    except KeyboardInterrupt:
        print("\n\nGeneration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
