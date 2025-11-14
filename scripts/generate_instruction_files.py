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
import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import json


# ============================================================================
# ROLE DEFAULTS - Common responsibilities for each role
# ============================================================================

ROLE_DEFAULTS = {
    'ProductManager': {
        'primary_responsibilities': [
            'Analyze stakeholder input and extract core requirements',
            'Define the problem statement clearly',
            'Identify user needs and success criteria',
            'Ask clarifying questions when requirements are ambiguous',
            'Write comprehensive Product Requirements Document (PRD)',
            'Ensure requirements are testable and unambiguous'
        ],
        'secondary_responsibilities': [
            'Identify scope boundaries (what\'s in/out)',
            'Prioritize requirements by criticality',
            'Consider user experience and usability'
        ],
        'lead_authority': 'Final say on PRD structure, prioritization, scope definition'
    },
    'BusinessAnalyst': {
        'primary_responsibilities': [
            'Analyze technical requirements and validation rules',
            'Define data structures and calculation logic at high level',
            'Identify edge cases and error scenarios',
            'Ensure requirements are technically feasible',
            'Validate that requirements are complete and testable'
        ],
        'secondary_responsibilities': [
            'Support lead role in requirements writing',
            'Provide technical perspective on user needs',
            'Document assumptions and constraints'
        ],
        'support_authority': 'Expert input on technical requirements, must approve PRD'
    },
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
    },
    'TechnicalLead': {
        'primary_responsibilities': [
            'Design system architecture addressing all PRD requirements',
            'Make technology stack decisions',
            'Define technical approach and design patterns',
            'Identify technical risks and dependencies',
            'Create ARCHITECTURE.md as primary deliverable',
            'Ensure architecture is feasible and maintainable'
        ],
        'secondary_responsibilities': [
            'Validate technical feasibility of task breakdown',
            'Provide input on effort estimates for technical tasks',
            'Identify infrastructure and tooling needs'
        ],
        'support_authority': 'Expert input on architecture and technology, must approve plan'
    },
    'LeadDeveloper': {
        'primary_responsibilities': [
            'Implement features according to task list and architecture',
            'Write clean, maintainable, tested code',
            'Follow best practices and coding standards',
            'Create unit and integration tests',
            'Document code and usage',
            'Collaborate with Code Reviewer on quality'
        ],
        'secondary_responsibilities': [
            'Debug and fix issues',
            'Optimize performance where needed',
            'Handle edge cases properly'
        ],
        'lead_authority': 'Final say on implementation details, code structure, and technical approach'
    },
    'CodeReviewer': {
        'primary_responsibilities': [
            'Review code for correctness, quality, and bugs',
            'Test functionality thoroughly',
            'Verify PRD requirements are met',
            'Identify edge cases that aren\'t handled',
            'Provide constructive feedback',
            'Approve code when ready'
        ],
        'secondary_responsibilities': [
            'Suggest improvements (non-blocking)',
            'Verify test coverage',
            'Check documentation quality'
        ],
        'support_authority': 'Quality gate - must approve before completion'
    }
}


# ============================================================================
# PHASE WORKFLOWS - Standard workflow for each phase
# ============================================================================

PHASE_WORKFLOWS = {
    'Requirements': {
        'phases': [
            {
                'name': 'Initial Analysis',
                'turns': '1-2',
                'steps': [
                    'Read USER_REQUEST.md thoroughly',
                    'Understand the core problem stakeholder is trying to solve',
                    'Identify what information is clear vs. unclear',
                    'List initial questions and ambiguities'
                ],
                'exit_criteria': 'Complete understanding of what was provided'
            },
            {
                'name': 'Collaborative Analysis',
                'turns': '3-5',
                'steps': [
                    'Discuss with teammate their perspective',
                    'Share your concerns and questions',
                    'Identify gaps that would block PRD creation',
                    'Reach consensus: Enough info to proceed or need clarification?'
                ],
                'exit_criteria': 'Team agreement on path forward'
            },
            {
                'name': 'PRD Creation or Clarification Request',
                'turns': '6-10',
                'steps': [
                    'Either write comprehensive PRD.md or create CLARIFICATION_REQUEST.md',
                    'Get teammate review and approval',
                    'Signal [[PROJECT_COMPLETE]] when both agree'
                ],
                'exit_criteria': 'PRD.md created and approved by both team members, or clarification request delivered'
            }
        ]
    },
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
            {
                'name': 'Architecture and Task Design',
                'turns': '4-7',
                'steps': [
                    'Design system architecture collaboratively',
                    'Break down requirements into specific tasks',
                    'Identify task dependencies',
                    'Determine critical path'
                ],
                'exit_criteria': 'Architecture defined; complete task list created'
            },
            {
                'name': 'Planning Documentation',
                'turns': '8-12',
                'steps': [
                    'Create ARCHITECTURE.md and PROJECT_TASKS.md',
                    'Define milestones and timeline',
                    'Identify risks and mitigation plans',
                    'Get teammate review and approval',
                    'Signal [[PROJECT_COMPLETE]] when both agree'
                ],
                'exit_criteria': 'Complete implementation plan approved by both'
            }
        ]
    },
    'Implementation': {
        'phases': [
            {
                'name': 'Setup and Planning',
                'turns': '1-2',
                'steps': [
                    'Read PRD.md, TASKS.md, and ARCHITECTURE.md',
                    'Understand all requirements and tasks',
                    'Set up project structure',
                    'Plan implementation order'
                ],
                'exit_criteria': 'Ready to start coding'
            },
            {
                'name': 'Core Implementation',
                'turns': '3-X',
                'steps': [
                    'Implement tasks in dependency order',
                    'Write tests for each feature',
                    'Self-review before requesting review',
                    'Fix issues found during self-review'
                ],
                'exit_criteria': 'All core features implemented'
            },
            {
                'name': 'Code Review and Refinement',
                'turns': 'X+1-Y',
                'steps': [
                    'Request review from teammate',
                    'Address feedback and fix bugs',
                    'Iterate until approval'
                ],
                'exit_criteria': 'Teammate approves code'
            },
            {
                'name': 'Final Validation',
                'turns': 'Y+1-MAX',
                'steps': [
                    'Verify all PRD acceptance criteria met',
                    'Complete documentation',
                    'Final testing',
                    'Get teammate final approval',
                    'Signal [[PROJECT_COMPLETE]]'
                ],
                'exit_criteria': 'Complete, tested, approved implementation'
            }
        ]
    }
}


# ============================================================================
# COLLABORATION PATTERNS - How role pairs work together
# ============================================================================

COLLABORATION_PATTERNS = {
    ('ProductManager', 'BusinessAnalyst'): {
        'lead_focus': 'User needs, problem definition, feature priorities',
        'support_focus': 'Technical details, calculation logic, validation rules',
        'lead_defers_on': 'Technical/calculation questions, validation specifications',
        'lead_leads_on': 'PRD structure, user-facing descriptions, scope boundaries',
        'autonomous_lead': [
            'PRD structure and format',
            'Priority of requirements',
            'User-facing feature descriptions',
            'Scope boundaries (MVP vs. future)'
        ],
        'requires_consensus': [
            'Whether to proceed with PRD or request clarification',
            'Assumptions to make when information is incomplete',
            'Technical requirement specifications'
        ]
    },
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
    },
    ('LeadDeveloper', 'CodeReviewer'): {
        'lead_focus': 'Implementation, code structure, technical decisions, feature delivery',
        'support_focus': 'Code quality, bug identification, testing verification, quality assurance',
        'lead_defers_on': 'Whether code quality is acceptable, when to approve delivery',
        'lead_leads_on': 'Implementation approach, code organization, technical trade-offs',
        'autonomous_lead': [
            'Variable/function names',
            'Code organization within files',
            'Implementation approach (within PRD constraints)',
            'Refactoring decisions for clarity'
        ],
        'requires_consensus': [
            'Code is ready for delivery',
            'Major refactoring decisions',
            'Trade-offs between different approaches',
            'Final approval before signaling [[PROJECT_COMPLETE]]'
        ]
    }
}


# ============================================================================
# DEFINITION OF DONE - Phase-specific completion criteria
# ============================================================================

DEFINITION_OF_DONE = {
    'Requirements': {
        'phase_complete_criteria': [
            'PRD.md exists and is comprehensive',
            'All critical requirements are documented',
            'Edge cases are identified and addressed',
            'Acceptance criteria are clear and testable',
            'Assumptions are explicitly documented',
            '{other_role} has reviewed and approved',
            'Both team members signal [[PROJECT_COMPLETE]]'
        ],
        'signal_conditions': [
            'PRD.md is written and complete',
            '{other_role} confirms they agree',
            'All must-have information is captured',
            'Planning team can work from this PRD'
        ]
    },
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
    },
    'Implementation': {
        'phase_complete_criteria': [
            'All features from PRD are implemented',
            'All tests written and passing',
            'Code reviewed and approved by {other_role}',
            'No critical bugs remaining',
            'Documentation complete (README.md, code comments)',
            'All PRD acceptance criteria verified',
            'Both team members signal [[PROJECT_COMPLETE]]'
        ],
        'signal_conditions': [
            'All code is functional and tested',
            '{other_role} has approved the code quality',
            'All PRD requirements are demonstrably met',
            'Project is ready for delivery'
        ]
    }
}


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
        """Get template content for a specific role using defaults"""

        # Get role defaults
        role_defaults = ROLE_DEFAULTS.get(role_name, {})

        # Build responsibilities sections
        primary_resp = role_defaults.get('primary_responsibilities', [])
        secondary_resp = role_defaults.get('secondary_responsibilities', [])

        primary_section = '\n'.join(f'- {resp}' for resp in primary_resp) if primary_resp else '- [TODO: Customize for this role]'
        secondary_section = '\n'.join(f'- {resp}' for resp in secondary_resp) if secondary_resp else '- [TODO: Add supporting activities]'

        # Build authority section
        if is_lead:
            authority = role_defaults.get('lead_authority', '[TODO: Define authority level]')
            authority_line = f"**LEAD ROLE** - {authority}"
        else:
            authority = role_defaults.get('support_authority', '[TODO: Define authority level]')
            authority_line = authority

        # Build workflow phases from defaults
        phase_workflows = PHASE_WORKFLOWS.get(phase_name, {}).get('phases', [])
        workflow_section = ""
        for i, phase_def in enumerate(phase_workflows, 1):
            steps_text = '\n  - [ ] '.join(phase_def['steps'])
            workflow_section += f"""
**Phase {i}: {phase_def['name']}** (Turn {phase_def['turns']})
  - [ ] {steps_text}
- Exit criteria: {phase_def['exit_criteria']}

"""

        if not workflow_section:
            workflow_section = """**Phase 1: [TODO: Activity Name]** (Turn 1-3)
- [ ] [TODO: Add steps]
- Exit criteria: [TODO: Define]
"""

        # Build collaboration section
        role_pair = (config.roles[phase_num][0], config.roles[phase_num][1]) if len(config.roles[phase_num]) > 1 else None
        collab_pattern = COLLABORATION_PATTERNS.get(role_pair, {}) if role_pair else {}

        if collab_pattern and is_lead:
            lead_focus = collab_pattern.get('lead_focus', '[TODO: Define your focus]')
            support_focus = collab_pattern.get('support_focus', '[TODO: Define their focus]')
            lead_defers = collab_pattern.get('lead_defers_on', '[TODO: When to follow their lead]')
            lead_leads = collab_pattern.get('lead_leads_on', '[TODO: When you have final say]')
            autonomous = collab_pattern.get('autonomous_lead', [])
            consensus_required = collab_pattern.get('requires_consensus', [])

            autonomous_text = '\n  - '.join(autonomous) if autonomous else '[TODO: List autonomous decisions]'
            consensus_text = '\n  - '.join(consensus_required) if consensus_required else '[TODO: List collaborative decisions]'

            collab_section = f"""**With {other_role_name}:**
- They focus on: {support_focus}
- You focus on: {lead_focus}
- Defer to them on: {lead_defers}
- Lead on: {lead_leads}

**Decision Making:**
- You can decide autonomously:
  - {autonomous_text}

- Requires {other_role_name} consensus:
  - {consensus_text}"""
        elif collab_pattern:
            lead_focus = collab_pattern.get('lead_focus', '[TODO: Define their focus]')
            support_focus = collab_pattern.get('support_focus', '[TODO: Define your focus]')
            lead_defers = collab_pattern.get('lead_defers_on', '[TODO: When you should lead]')
            lead_leads = collab_pattern.get('lead_leads_on', '[TODO: When to defer]')

            collab_section = f"""**With {other_role_name}:**
- They focus on: {lead_focus}
- You focus on: {support_focus}
- Defer to them on: {lead_leads}
- Provide expert input on: {lead_defers}

**Decision Making:**
- {other_role_name} (lead) makes final decisions on structure and priorities
- You provide expert input and must approve final deliverable
- Both must signal [[PROJECT_COMPLETE]] for phase to end"""
        else:
            collab_section = f"""**With {other_role_name}:**
- They focus on: [TODO: Define their focus]
- You focus on: [TODO: Define your focus]
- Defer to them on: [TODO: When to follow their lead]
- Lead on: [TODO: When you have final say]

**Decision Making:**
- You can decide autonomously: [TODO: List autonomous decisions]
- Requires {other_role_name} consensus: [TODO: List collaborative decisions]"""

        return f"""
## Your Role: {role_name} ({phase_name} Phase)

**Primary Responsibilities:**
{primary_section}

**Secondary Responsibilities:**
{secondary_section}

**Team Position:**
- Reports to: Project Stakeholder
- Collaborates with: {other_role_name}
- Decision Authority: {authority_line}

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

{workflow_section.strip()}

## {config.domain.title()} Domain Guidance

<!-- TODO: Add domain-specific guidance for {config.domain} projects -->

## {config.tech_stack.title()} Technology Guidance

<!-- TODO: Add technology-specific patterns and examples -->

## Collaboration Protocols

{collab_section}

## Common Pitfalls to Avoid

<!-- TODO: Add project-specific pitfalls and best practices -->

## Definition of Done

{self._build_definition_of_done(phase_name, other_role_name)}
"""

    def _build_definition_of_done(self, phase_name: str, other_role_name: str) -> str:
        """Build Definition of Done section from defaults"""
        dod_defaults = DEFINITION_OF_DONE.get(phase_name, {})

        if not dod_defaults:
            # Fallback if phase not in defaults
            return f"""This {phase_name.lower()} phase is complete when:
- [ ] [TODO: Add specific completion criteria]
- [ ] {other_role_name} has reviewed and approved
- [ ] Both team members signal [[PROJECT_COMPLETE]]

**You may signal [[PROJECT_COMPLETE]] when:**
1. [TODO: Add condition]
2. {other_role_name} confirms agreement
3. All deliverables are complete"""

        # Build completion criteria checklist
        criteria = dod_defaults.get('phase_complete_criteria', [])
        criteria_text = '\n'.join(f'- [ ] {c.format(other_role=other_role_name)}' for c in criteria)

        # Build signal conditions
        conditions = dod_defaults.get('signal_conditions', [])
        conditions_text = '\n'.join(f'{i+1}. {c.format(other_role=other_role_name)}' for i, c in enumerate(conditions))

        return f"""This {phase_name.lower()} phase is complete when:
{criteria_text}

**You may signal [[PROJECT_COMPLETE]] when:**
{conditions_text}"""

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

    # ========================================================================
    # REFINEMENT MODE METHODS
    # ========================================================================

    def refine_templates(self, args):
        """Refine existing instruction files based on artifacts"""
        print("=" * 70)
        print(f"Orchestrator Template Refinement - Phase {args.phase}")
        print("=" * 70)
        print()

        if args.phase == 2:
            self._refine_phase_2(args)
        elif args.phase == 3:
            self._refine_phase_3(args)

    def _refine_phase_2(self, args):
        """Refine Phase 2 templates using PRD.md"""
        print("Refining Phase 2 (Planning) templates using PRD.md...")
        print()

        # Load PRD
        prd_path = Path(args.prd_file)
        if not prd_path.exists():
            raise FileNotFoundError(f"PRD file not found: {prd_path}")

        print(f"Reading PRD from: {prd_path}")
        with open(prd_path, 'r') as f:
            prd_content = f.read()

        # Parse PRD to extract key information
        prd_data = self._parse_prd(prd_content)
        print(f"  Extracted {len(prd_data['functional_requirements'])} functional requirements")
        print(f"  Extracted {len(prd_data['nonfunctional_requirements'])} non-functional requirements")
        print(f"  Found {len(prd_data['data_models'])} data model references")
        print()

        # Find project directory
        project_dir = self._find_project_directory(args, prd_path)
        print(f"Project directory: {project_dir}")
        print()

        # Load project config
        config = self._load_project_config(project_dir)

        # Find Phase 2 instruction files
        phase2_files = self._find_phase_files(project_dir, 2, config)

        if not phase2_files:
            print("⚠️  No Phase 2 instruction files found.")
            print(f"   Expected files in: {project_dir}")
            return

        print(f"Found {len(phase2_files)} Phase 2 instruction files to refine:")
        for f in phase2_files:
            print(f"  - {f.name}")
        print()

        # Refine each file
        refined_count = 0
        for file_path in phase2_files:
            if self._refine_phase2_file(file_path, prd_data, config):
                refined_count += 1

        print()
        print("=" * 70)
        print(f"Phase 2 Refinement Complete!")
        print("=" * 70)
        print(f"  {refined_count} file(s) updated")
        print()
        print("Next steps:")
        print("  1. Review the updated files for accuracy")
        print("  2. Fill remaining Domain/Tech TODOs")
        print("  3. Run Phase 2 orchestration session")
        print()

    def _refine_phase_3(self, args):
        """Refine Phase 3 templates using ARCHITECTURE.md and PROJECT_TASKS.md"""
        print("⚠️  Phase 3 refinement not yet implemented.")
        print("   This will be added in Phase C of the implementation.")
        print()

    def _parse_prd(self, prd_content: str) -> Dict:
        """Parse PRD.md to extract key information"""
        data = {
            'functional_requirements': [],
            'nonfunctional_requirements': [],
            'data_models': [],
            'success_criteria': [],
            'input_artifacts': ['PRD.md'],
            'output_artifacts': []
        }

        # Extract functional requirements (FR-1, FR-2, etc.)
        # Support format: "**Requirement ID:** FR-1  \n**Description:** ..."
        fr_pattern = r'\*\*Requirement\s+ID:\*\*\s+(FR-\d+)\s*\n\*\*Description:\*\*\s+(.+?)(?=\n\*\*(?:Input|Data|Success|Output|Business)|###|\n\n###|$)'
        fr_matches = re.findall(fr_pattern, prd_content, re.DOTALL | re.IGNORECASE)
        for fr_id, fr_desc in fr_matches:
            data['functional_requirements'].append({
                'id': fr_id.strip(),
                'description': fr_desc.strip()
            })

        # Extract non-functional requirements (NFR-1, NFR-2, etc.)
        # Support format: "**Requirement ID:** NFR-1  \n**Description:** ..."
        nfr_pattern = r'\*\*Requirement\s+ID:\*\*\s+(NFR-\d+)\s*\n\*\*Description:\*\*\s+(.+?)(?=\n\*\*(?:Specifications?|Input|Data|Success|Output)|###|\n\n###|$)'
        nfr_matches = re.findall(nfr_pattern, prd_content, re.DOTALL | re.IGNORECASE)
        for nfr_id, nfr_desc in nfr_matches:
            data['nonfunctional_requirements'].append({
                'id': nfr_id.strip(),
                'description': nfr_desc.strip()
            })

        # Extract data model references (class names, entity names)
        # Look for common patterns: Transaction, Account, User, etc.
        data_model_pattern = r'(?:class|entity|model|table|collection)\s+([A-Z][a-zA-Z0-9_]+)'
        data_models = set(re.findall(data_model_pattern, prd_content, re.IGNORECASE))
        data['data_models'] = list(data_models)

        # Extract success criteria
        success_section = re.search(
            r'##\s*Success\s*Criteria.*?(?=##|$)',
            prd_content,
            re.DOTALL | re.IGNORECASE
        )
        if success_section:
            # Extract bullet points
            criteria = re.findall(r'[-*]\s*(.+)', success_section.group())
            data['success_criteria'] = [c.strip() for c in criteria if c.strip()]

        # Infer output artifacts from requirements
        if any('csv' in req['description'].lower() for req in data['functional_requirements']):
            data['output_artifacts'].append('CSV report file')
        if any('api' in req['description'].lower() for req in data['functional_requirements']):
            data['output_artifacts'].append('API endpoint documentation')

        return data

    def _find_project_directory(self, args, prd_path: Path) -> Path:
        """Find the project directory containing instruction files"""
        if args.project_dir:
            return Path(args.project_dir)

        # Assume PRD.md is in the project root
        return prd_path.parent

    def _load_project_config(self, project_dir: Path) -> Optional[ProjectConfig]:
        """Load project_config.json if it exists"""
        config_file = project_dir / "project_config.json"

        if not config_file.exists():
            print(f"⚠️  No project_config.json found in {project_dir}")
            print("   Assuming default 3-phase configuration")
            return None

        with open(config_file, 'r') as f:
            config_data = json.load(f)

        return ProjectConfig(
            project_name=config_data['project_name'],
            project_path=config_data['project_path'],
            project_type=config_data['project_type'],
            domain=config_data['domain'],
            tech_stack=config_data['tech_stack'],
            num_phases=config_data['num_phases'],
            roles={int(k): v for k, v in config_data['roles'].items()},
            description=config_data.get('description', ''),
            existing_code=config_data.get('existing_code', False),
            existing_code_path=config_data.get('existing_code_path', '')
        )

    def _find_phase_files(self, project_dir: Path, phase_num: int, config: Optional[ProjectConfig]) -> List[Path]:
        """Find all instruction files for a given phase"""
        if config and phase_num in config.roles:
            phase_name = self._get_phase_name(phase_num, config.num_phases)
            phase_files = []
            for role_name in config.roles[phase_num]:
                filename = f"ROLE_{role_name}_{phase_name}.md"
                file_path = project_dir / filename
                if file_path.exists():
                    phase_files.append(file_path)
            return phase_files
        else:
            # Fallback: search for files matching pattern
            phase_name = self._get_phase_name(phase_num, 3)  # Assume 3 phases
            pattern = f"ROLE_*_{phase_name}.md"
            return list(project_dir.glob(pattern))

    def _refine_phase2_file(self, file_path: Path, prd_data: Dict, config: Optional[ProjectConfig]) -> bool:
        """Refine a single Phase 2 instruction file"""
        print(f"Refining: {file_path.name}...")

        with open(file_path, 'r') as f:
            content = f.read()

        original_content = content
        modified = False

        # Fill Input Artifacts TODO
        if '[TODO: List required input files]' in content:
            # Don't add "- " prefix since template already has it
            input_list = '\n- '.join(artifact for artifact in prd_data['input_artifacts'])
            content = content.replace(
                '[TODO: List required input files]',
                input_list
            )
            modified = True
            print("  ✓ Filled Input Artifacts")

        # Fill Output Artifacts TODO
        if '[TODO: List expected output files]' in content:
            # Don't add "- " prefix since template already has it
            output_items = prd_data['output_artifacts'] if prd_data['output_artifacts'] else ['ARCHITECTURE.md', 'PROJECT_TASKS.md', 'RISKS.md']
            output_list = '\n- '.join(artifact for artifact in output_items)
            content = content.replace(
                '[TODO: List expected output files]',
                output_list
            )
            modified = True
            print("  ✓ Filled Output Artifacts")

        # Fill Success Criteria TODO
        if '[TODO: Define completion criteria]' in content:
            if prd_data['success_criteria']:
                criteria_list = '\n'.join(f"- {criterion}" for criterion in prd_data['success_criteria'][:5])  # Limit to 5
                content = content.replace(
                    '[TODO: Define completion criteria]',
                    f"Architecture addresses all PRD requirements:\n{criteria_list}"
                )
            else:
                content = content.replace(
                    '[TODO: Define completion criteria]',
                    "All PRD functional and non-functional requirements are addressed in ARCHITECTURE.md"
                )
            modified = True
            print("  ✓ Filled Success Criteria")

        # Fill Workflow Phase Activity Names (basic)
        if '[TODO: Activity Name]' in content:
            content = content.replace(
                '**Phase 1: [TODO: Activity Name]**',
                '**Phase 1: PRD Analysis and Component Identification**'
            )
            # Get FR count for display
            fr_count = len(prd_data['functional_requirements'])
            fr_range = f'FR-1 through FR-{fr_count}' if fr_count > 0 else 'all functional requirements'

            content = content.replace(
                '- [ ] [TODO: Add steps]',
                f'- [ ] Review {fr_range}\n'
                '  - [ ] Identify system components needed\n'
                '  - [ ] Map requirements to architectural layers',
                1  # Only replace first occurrence
            )
            modified = True
            print("  ✓ Filled Workflow Phase structure")

        if modified:
            # Write updated content
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"  💾 Saved changes to {file_path.name}")
            return True
        else:
            print(f"  ℹ️  No TODOs found to fill (file may already be customized)")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate or refine Orchestrator instruction files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initial generation (Stage 1)
  python scripts/generate_instruction_files.py

  # Refine Phase 2 templates after PRD exists (Stage 2)
  python scripts/generate_instruction_files.py --refine --phase 2 --prd-file ./PRD.md

  # Refine Phase 3 templates after ARCHITECTURE exists (Stage 3)
  python scripts/generate_instruction_files.py --refine --phase 3 \\
    --architecture-file ./ARCHITECTURE.md --tasks-file ./PROJECT_TASKS.md
        """
    )

    parser.add_argument(
        '--refine',
        action='store_true',
        help='Refine existing instruction files instead of generating new ones'
    )

    parser.add_argument(
        '--phase',
        type=int,
        choices=[2, 3],
        help='Which phase to refine (2 or 3). Requires --refine.'
    )

    parser.add_argument(
        '--prd-file',
        type=str,
        help='Path to PRD.md file (for Phase 2 refinement)'
    )

    parser.add_argument(
        '--architecture-file',
        type=str,
        help='Path to ARCHITECTURE.md file (for Phase 3 refinement)'
    )

    parser.add_argument(
        '--tasks-file',
        type=str,
        help='Path to PROJECT_TASKS.md file (for Phase 3 refinement)'
    )

    parser.add_argument(
        '--project-dir',
        type=str,
        help='Project directory containing instruction files (for refinement mode)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.refine:
        if not args.phase:
            parser.error("--refine requires --phase")
        if args.phase == 2 and not args.prd_file:
            parser.error("Phase 2 refinement requires --prd-file")
        if args.phase == 3 and not (args.architecture_file and args.tasks_file):
            parser.error("Phase 3 refinement requires both --architecture-file and --tasks-file")

    try:
        generator = InstructionFileGenerator()

        if args.refine:
            # Refinement mode
            generator.refine_templates(args)
        else:
            # Initial generation mode
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
