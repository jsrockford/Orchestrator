# Session Mapping: Web UI Development Workflow

This document provides detailed configuration for running the three-phase Web UI development workflow in your orchestrator system. It defines which instruction files to load, what inputs to provide, and how sessions communicate.

## Overview

The workflow consists of **3 phases** with **2 AI sessions per phase** (6 sessions total). Each session has a specific role and receives specific instruction files.

## Quick Reference: Role Files by Phase

### Phase 1: Requirements (PRD Creation)
- **Session 1-1 (Primary)**: `ROLE_ProductManager_WebUI.md`
- **Session 1-2 (Secondary)**: `ROLE_UXDesigner_WebUI.md`

### Phase 2: Planning (Task Breakdown)
- **Session 2-1 (Primary)**: `ROLE_EngineeringManager_WebUI.md`
- **Session 2-2 (Secondary)**: `ROLE_FullStackArchitect_WebUI.md`

### Phase 3: Implementation (Coding)
- **Session 3-1 (Primary)**: `ROLE_FullStackDeveloper_WebUI.md`
- **Session 3-2 (Secondary)**: `ROLE_QAEngineer_WebUI.md`

**All role files are included in this directory.** No need to create additional files or use fallbacks.

## Session Configuration

### Phase 1: Web UI Requirements (PRD Creation)

**Phase Goal**: Create comprehensive Web UI requirements document that defines what needs to be built.

#### Session 1-1: Product Manager

**Role**: Product Manager (Primary Decision Maker)

**Instruction File**: `ROLE_ProductManager_WebUI.md`

**Responsibilities**:
- Lead requirements definition
- Analyze existing Python application
- Define input fields and output displays
- Specify API contract
- Make final decisions on scope
- Signal [[PROJECT_COMPLETE]] when ready

**Working Directory**: `[PROJECT_PATH]` (specified in instruction file as `[PROJECT_PATH]`)

**Input Files Required** (must exist in project directory):
- `EXISTING_APP_ANALYSIS.md` - Analysis of current terminal application
  - What it does
  - What inputs it accepts
  - What outputs it produces
  - How calculations work
  - Example: See template below

- `USER_REQUEST.md` - Stakeholder's web UI requirements
  - Why they want a web UI
  - Who will use it
  - Any specific design preferences
  - Example: "I want to add a web interface to my credit card calculator so users can access it from their phones"

**Output Files Produced**:
- `WEB_PRD.md` - Complete Web UI Product Requirements Document
- `CLARIFICATION_REQUEST.md` - (optional) If more info needed from stakeholder

**Communication Protocol**:
- Receives messages from Session 1-2 (UX Designer)
- All responses must use `<<<RESPONSE_START>>>` and `<<<RESPONSE_END>>>` delimiters
- Signals completion with `[[PROJECT_COMPLETE]]` inside delimiters

**Completion Signal**: `[[PROJECT_COMPLETE]]` (requires 66% consensus = both sessions agree)

**Typical Duration**: 5-10 turns

---

#### Session 1-2: UX Designer

**Role**: UX Designer (Collaborator)

**Instruction File**: `ROLE_UXDesigner_WebUI.md`

**Responsibilities**:
- Provide UX perspective on interface design
- Define input form layout and visual design
- Specify results display design
- Define responsive design requirements
- Ensure accessibility standards (WCAG)
- Validate form field designs
- Review results display approach
- Approve final PRD

**Working Directory**: Same as Session 1-1

**Input Files Required**: Same as Session 1-1

**Output Files Produced**: Contributes to same outputs as Session 1-1

**Communication Protocol**: Same as Session 1-1

**Completion Signal**: `[[PROJECT_COMPLETE]]`

---

### Phase 2: Web UI Planning (Task Breakdown)

**Phase Goal**: Create detailed implementation plan with task breakdown and timeline.

#### Session 2-1: Engineering Manager

**Role**: Engineering Manager (Primary Decision Maker)

**Instruction File**: `ROLE_EngineeringManager_WebUI.md`

**Responsibilities**:
- Break down PRD into specific tasks
- Organize tasks by workstream (Setup, Backend, Frontend, Integration)
- Identify dependencies and critical path
- Identify parallel opportunities
- Define milestones
- Estimate timeline
- Signal [[PROJECT_COMPLETE]] when ready

**Working Directory**: `[PROJECT_PATH]`

**Input Files Required** (must exist from Phase 1):
- `WEB_PRD.md` - From Phase 1
- `EXISTING_APP_ANALYSIS.md` - Understanding of existing code

**Output Files Produced**:
- `WEB_TASKS.md` - Detailed task breakdown with dependencies
- `WEB_PLAN.md` - Implementation plan with milestones and timeline

**Communication Protocol**:
- Receives messages from Session 2-2 (Full Stack Architect)
- All responses must use `<<<RESPONSE_START>>>` and `<<<RESPONSE_END>>>` delimiters
- Signals completion with `[[PROJECT_COMPLETE]]` inside delimiters

**Completion Signal**: `[[PROJECT_COMPLETE]]` (requires 66% consensus)

**Typical Duration**: 7-12 turns

---

#### Session 2-2: Full Stack Architect

**Role**: Full Stack Architect (Collaborator)

**Instruction File**: `ROLE_FullStackArchitect_WebUI.md`

**Responsibilities**:
- Make technology stack decisions (FastAPI, React, Tailwind)
- Design full-stack architecture
- Define API contract between frontend and backend
- Plan integration strategy with existing Python code
- Identify technical dependencies and risks
- Create TECH_DECISIONS.md with rationale
- Validate technical feasibility of plan
- Provide architecture guidance
- Validate task dependencies
- Identify technical risks
- Approve final plan

**Working Directory**: Same as Session 2-1

**Input Files Required**: Same as Session 2-1

**Output Files Produced**: Contributes to same outputs as Session 2-1

**Communication Protocol**: Same as Session 2-1

**Completion Signal**: `[[PROJECT_COMPLETE]]`

---

### Phase 3: Web UI Implementation (Full Stack Development)

**Phase Goal**: Build complete web interface - backend, frontend, and integration.

#### Session 3-1: Full Stack Developer

**Role**: Full Stack Developer (Primary Implementer)

**Instruction File**: `ROLE_FullStackDeveloper_WebUI.md`

**Responsibilities**:
- Implement FastAPI backend
- Implement React + Tailwind frontend
- Integrate with existing Python code
- Configure CORS
- Handle all error cases
- Test at each layer
- Signal [[PROJECT_COMPLETE]] when ready

**Working Directory**: `[PROJECT_PATH]`

**Input Files Required** (must exist from Phases 1 & 2):
- `WEB_PRD.md` - Requirements
- `WEB_TASKS.md` - Task breakdown
- `WEB_PLAN.md` - Implementation plan
- `EXISTING_APP_ANALYSIS.md` - Understanding of existing code
- Existing Python application files (e.g., `calculator.py`)

**Output Files Produced**:
- `backend/` - Complete FastAPI backend
  - `main.py`
  - `api/routes.py`
  - `models/schemas.py`
  - `requirements.txt`
  - `tests/`
- `frontend/` - Complete React frontend
  - `src/App.jsx`
  - `src/components/`
  - `src/api/client.js`
  - `package.json`
  - `tailwind.config.js`
- `README.md` - Setup and usage documentation
- Test files and documentation

**Communication Protocol**:
- Receives messages from Session 3-2 (Code Reviewer)
- All responses must use `<<<RESPONSE_START>>>` and `<<<RESPONSE_END>>>` delimiters
- Signals completion with `[[PROJECT_COMPLETE]]` inside delimiters

**Completion Signal**: `[[PROJECT_COMPLETE]]` (requires 66% consensus)

**Typical Duration**: 15-25 turns

---

#### Session 3-2: QA Engineer

**Role**: QA Engineer (Quality Assurance/Collaborator)

**Instruction File**: `ROLE_QAEngineer_WebUI.md`

**Responsibilities**:
- Test backend API thoroughly (endpoints, validation, edge cases)
- Test frontend UI comprehensively (components, interactions, responsiveness)
- Verify integration between frontend and backend
- **CRITICAL**: Compare web UI results against terminal app (must match exactly)
- Test on multiple browsers and devices
- Test responsive design (desktop, tablet, mobile)
- Identify bugs and report with reproduction steps
- Verify all PRD acceptance criteria are met
- Approve implementation when quality standards met

**Working Directory**: Same as Session 3-1

**Input Files Required**: Same as Session 3-1, plus code produced by Session 3-1

**Output Files Produced**:
- Code review feedback
- Bug reports
- Test results

**Communication Protocol**: Same as Session 3-1

**Completion Signal**: `[[PROJECT_COMPLETE]]`

---

## File Templates

### Template: EXISTING_APP_ANALYSIS.md

```markdown
# Existing Application Analysis

## Application Name
Credit Card Balance Transfer Calculator

## Purpose
Calculates whether it's cheaper to keep debt on current credit card or transfer to a promotional 0% APR card.

## Current Interface
Command-line / Terminal interface

## Programming Language
Python 3.9+

## Main Files
- `calculator.py` - Main calculation logic and CLI interface

## Input Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| debt | Decimal | Yes | Current credit card balance | 5000.00 |
| current_apr | Decimal | Yes | Current APR as decimal | 0.185 (18.5%) |
| monthly_payment | Decimal | Yes | Monthly payment amount | 150.00 |
| transfer_fee_pct | Decimal | Yes | Balance transfer fee % | 0.03 (3%) |
| promo_months | Integer | Yes | Promotional period length | 12 |
| promo_apr | Decimal | Yes | Promotional APR | 0.00 (0%) |
| post_promo_apr | Decimal | Yes | APR after promo ends | 0.20 (20%) |

## Output Format

The terminal app displays:

**Scenario A (Current Card):**
- Total interest paid: $458.23
- Months to payoff: 38 months
- Total amount paid: $5,458.23

**Scenario B (Balance Transfer):**
- Transfer fee: $150.00
- Total interest paid: $245.67
- Months to payoff: 36 months
- Total amount paid: $5,395.67

**Recommendation:**
- Best option: Scenario B (Transfer)
- Savings: $62.56
- Explanation: "Transferring saves you money despite the transfer fee"

## Key Functions

```python
def calculate_scenario_a(debt, apr, payment):
    """Calculate paying off current card."""
    # Returns: total_interest, months_to_payoff, total_paid

def calculate_scenario_b(debt, transfer_fee_pct, promo_months,
                        promo_apr, post_promo_apr, payment):
    """Calculate balance transfer scenario."""
    # Returns: total_interest, months_to_payoff, total_paid, transfer_fee

def compare_scenarios(result_a, result_b):
    """Compare scenarios and recommend best option."""
    # Returns: best_option, savings, explanation
```

## Edge Cases Handled

1. Payment too low (less than monthly interest) - Error
2. 0% APR - Handled correctly
3. Exact payoff amounts - Handled correctly
4. Decimal precision - Uses Decimal type for accuracy

## Dependencies

- Python 3.9+
- No external libraries (uses standard library only)
- Decimal module for precision

## How to Run (Current)

```bash
python calculator.py --debt 5000 --current-apr 18.5 --payment 150 \
  --transfer-fee 3 --promo-months 12 --promo-apr 0 --post-promo-apr 20
```

## Notes

- All calculations use Decimal type for financial precision
- Validation happens at input time
- No data persistence - each calculation is independent
- No authentication or user accounts
```

### Template: USER_REQUEST.md

```markdown
# Web UI Request

## Requestor
[Your Name]

## Date
[Date]

## Current Situation
I have a working Python terminal application (credit card calculator) that helps users compare balance transfer options. It works well but requires command-line knowledge.

## Desired Outcome
I want to add a modern web interface so:
1. Non-technical users can access it easily
2. Users can access it from their phones
3. It looks professional and trustworthy
4. Results are easier to read and understand visually

## Specific Requirements

### Must Have
- Web-based form with all input fields from terminal app
- Clear labels and help text for each field
- Calculate button that runs the calculation
- Display results in easy-to-read format
- Show recommendation prominently
- Work on mobile phones

### Nice to Have
- Modern, professional appearance
- Color coding (green for savings, etc.)
- Loading indicator while calculating
- Ability to clear and start new calculation

### Technology Preferences
- Backend: FastAPI (Python, since existing code is Python)
- Frontend: React with Tailwind CSS for modern styling
- Must NOT modify existing calculation code (it's tested and working)

## Success Criteria
- Results from web UI match terminal app exactly
- Non-technical users can complete a calculation without help
- Works on desktop and mobile browsers
- Looks professional and modern

## Timeline
Not urgent - quality over speed

## Budget/Resources
Development only - will self-host initially
```

---

## Orchestrator Integration

### Configuration Example (YAML)

```yaml
web_ui_workflow:
  phases:
    - phase: 1
      name: "Web UI Requirements"
      sessions:
        - session_id: "prd_pm"
          role: "Product Manager"
          instruction_file: "ROLE_ProductManager_WebUI.md"
          working_directory: "{project_path}"
          required_inputs:
            - "EXISTING_APP_ANALYSIS.md"
            - "USER_REQUEST.md"
          outputs:
            - "WEB_PRD.md"

        - session_id: "prd_ux"
          role: "UX Designer"
          instruction_file: "ROLE_UXDesigner_WebUI.md"
          working_directory: "{project_path}"
          required_inputs:
            - "EXISTING_APP_ANALYSIS.md"
            - "USER_REQUEST.md"
          outputs: []

      completion_criteria:
        type: "consensus"
        threshold: 0.66
        signal: "[[PROJECT_COMPLETE]]"

      max_turns: 15

    - phase: 2
      name: "Web UI Planning"
      sessions:
        - session_id: "plan_em"
          role: "Engineering Manager"
          instruction_file: "ROLE_EngineeringManager_WebUI.md"
          working_directory: "{project_path}"
          required_inputs:
            - "WEB_PRD.md"
            - "EXISTING_APP_ANALYSIS.md"
          outputs:
            - "WEB_TASKS.md"
            - "WEB_PLAN.md"

        - session_id: "plan_arch"
          role: "Full Stack Architect"
          instruction_file: "ROLE_FullStackArchitect_WebUI.md"
          working_directory: "{project_path}"
          required_inputs:
            - "WEB_PRD.md"
            - "EXISTING_APP_ANALYSIS.md"
          outputs:
            - "TECH_DECISIONS.md"
            - "API_SPEC.md"
            - "ARCHITECTURE.md"

      completion_criteria:
        type: "consensus"
        threshold: 0.66
        signal: "[[PROJECT_COMPLETE]]"

      max_turns: 20

    - phase: 3
      name: "Web UI Implementation"
      sessions:
        - session_id: "impl_dev"
          role: "Full Stack Developer"
          instruction_file: "ROLE_FullStackDeveloper_WebUI.md"
          working_directory: "{project_path}"
          required_inputs:
            - "WEB_PRD.md"
            - "WEB_TASKS.md"
            - "WEB_PLAN.md"
            - "EXISTING_APP_ANALYSIS.md"
            # Plus existing Python files
          outputs:
            - "backend/"
            - "frontend/"
            - "README.md"

        - session_id: "impl_qa"
          role: "QA Engineer"
          instruction_file: "ROLE_QAEngineer_WebUI.md"
          working_directory: "{project_path}"
          required_inputs: []  # Will see same files as developer
          outputs:
            - "test_reports/"
            - "bug_reports/"

      completion_criteria:
        type: "consensus"
        threshold: 0.66
        signal: "[[PROJECT_COMPLETE]]"

      max_turns: 30
```

### Python Orchestrator Example

```python
class WebUIWorkflow:
    def __init__(self, project_path):
        self.project_path = project_path
        self.phases = [
            self.phase_1_requirements,
            self.phase_2_planning,
            self.phase_3_implementation
        ]

    def run(self):
        for phase in self.phases:
            phase()

    def phase_1_requirements(self):
        """Phase 1: Create Web UI PRD"""

        # Verify required inputs exist
        self.verify_file_exists("EXISTING_APP_ANALYSIS.md")
        self.verify_file_exists("USER_REQUEST.md")

        # Create sessions
        pm_session = ClaudeSession(
            instruction_file="ROLE_ProductManager_WebUI.md",
            working_dir=self.project_path,
            session_id="web_prd_pm"
        )

        ux_session = ClaudeSession(
            instruction_file="ROLE_UXDesigner_WebUI.md",  # or fallback
            working_dir=self.project_path,
            session_id="web_prd_ux"
        )

        # Run discussion
        orchestrator = DiscussionOrchestrator(
            sessions=[pm_session, ux_session],
            completion_signal="[[PROJECT_COMPLETE]]",
            consensus_threshold=0.66,
            max_turns=15
        )

        orchestrator.run()

        # Verify outputs produced
        self.verify_file_exists("WEB_PRD.md")

        print("Phase 1 complete: WEB_PRD.md created")

    def phase_2_planning(self):
        """Phase 2: Create implementation plan"""

        # Verify inputs from Phase 1
        self.verify_file_exists("WEB_PRD.md")

        # Create sessions
        em_session = ClaudeSession(
            instruction_file="ROLE_EngineeringManager_WebUI.md",
            working_dir=self.project_path,
            session_id="web_plan_em"
        )

        arch_session = ClaudeSession(
            instruction_file="ROLE_FullStackArchitect_WebUI.md",  # or fallback
            working_dir=self.project_path,
            session_id="web_plan_arch"
        )

        # Run discussion
        orchestrator = DiscussionOrchestrator(
            sessions=[em_session, arch_session],
            completion_signal="[[PROJECT_COMPLETE]]",
            consensus_threshold=0.66,
            max_turns=20
        )

        orchestrator.run()

        # Verify outputs
        self.verify_file_exists("WEB_TASKS.md")
        self.verify_file_exists("WEB_PLAN.md")

        print("Phase 2 complete: WEB_TASKS.md and WEB_PLAN.md created")

    def phase_3_implementation(self):
        """Phase 3: Implement web UI"""

        # Verify inputs from Phases 1 & 2
        self.verify_file_exists("WEB_PRD.md")
        self.verify_file_exists("WEB_TASKS.md")
        self.verify_file_exists("WEB_PLAN.md")

        # Create sessions
        dev_session = ClaudeSession(
            instruction_file="ROLE_FullStackDeveloper_WebUI.md",
            working_dir=self.project_path,
            session_id="web_impl_dev"
        )

        reviewer_session = ClaudeSession(
            instruction_file="ROLE_CodeReviewer_Implementation.md",
            working_dir=self.project_path,
            session_id="web_impl_reviewer"
        )

        # Run discussion
        orchestrator = DiscussionOrchestrator(
            sessions=[dev_session, reviewer_session],
            completion_signal="[[PROJECT_COMPLETE]]",
            consensus_threshold=0.66,
            max_turns=30
        )

        orchestrator.run()

        # Verify outputs
        self.verify_directory_exists("backend")
        self.verify_directory_exists("frontend")
        self.verify_file_exists("README.md")

        print("Phase 3 complete: Web UI implementation ready")

    def verify_file_exists(self, filename):
        path = os.path.join(self.project_path, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required file not found: {filename}")

    def verify_directory_exists(self, dirname):
        path = os.path.join(self.project_path, dirname)
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Required directory not found: {dirname}")

# Usage
workflow = WebUIWorkflow("/path/to/project")
workflow.run()
```

---

## Communication Flow

### Phase 1 Example

```
Turn 1:
  PM → "I've read the requirements. Let me analyze the existing app..."
  UX → "I'll focus on user experience aspects..."

Turn 2:
  PM → "Here are the input fields I've identified: [list]"
  UX → "Those look good. For mobile, we should stack them vertically..."

Turn 3:
  PM → "Agreed. What about the results display?"
  UX → "I suggest using cards for each scenario with color coding..."

[... discussion continues ...]

Turn 8:
  PM → "I've created WEB_PRD.md with all requirements. Please review."
  UX → "Looks comprehensive. The API contract is clear. I approve."

Turn 9:
  PM → "<<<RESPONSE_START>>>
        Web UI PRD is complete. All requirements documented.
        [[PROJECT_COMPLETE]]
        <<<RESPONSE_END>>>"

  UX → "<<<RESPONSE_START>>>
        I agree the PRD is complete and ready for planning team.
        [[PROJECT_COMPLETE]]
        <<<RESPONSE_END>>>"

[Orchestrator detects 2/2 = 100% consensus > 66% threshold]
[Phase 1 complete, proceed to Phase 2]
```

---

## Troubleshooting

### Issue: Session doesn't understand role
**Symptom**: AI acts generic instead of following role instructions
**Solution**:
- Verify instruction file is loaded correctly
- Ensure [PROJECT_PATH] is replaced with actual path
- Check that file path is accessible to AI session

### Issue: Phase doesn't complete
**Symptom**: Discussion goes on too long without [[PROJECT_COMPLETE]]
**Solution**:
- Check if both sessions understand completion criteria
- Verify consensus threshold (should be 0.66 for 2 sessions)
- Check max_turns hasn't been reached
- Manually review if PRD/Tasks/Code is actually complete

### Issue: Missing input files
**Symptom**: Session can't find required input files
**Solution**:
- Verify files exist in project directory
- Check file names match exactly (case-sensitive)
- Ensure working_directory is set correctly

### Issue: Code doesn't integrate with existing app
**Symptom**: Backend can't import existing Python functions
**Solution**:
- Verify existing Python files are in project directory
- Check function names match exactly
- May need to add to sys.path in backend code

---

## Tips for Success

1. **Prepare Good Input Files**: The quality of EXISTING_APP_ANALYSIS.md and USER_REQUEST.md greatly affects results

2. **Don't Skip Phases**: Each phase builds on the previous. Skipping phases leads to incomplete implementations

3. **Review Between Phases**: After each phase completes, manually review the outputs before proceeding

4. **Adjust Consensus Threshold**: If sessions struggle to agree, you may need to adjust the threshold or add a tie-breaker session

5. **Monitor Turn Count**: If a phase is taking too many turns, intervene to guide the discussion

6. **Preserve Existing Code**: Emphasize in all phases that existing Python code should NOT be modified

7. **Test Thoroughly**: Phase 3 should include extensive testing to verify web UI matches terminal app

---

## Next Steps

After completing all three phases, you should have:
- ✅ Complete Web UI requirements (WEB_PRD.md)
- ✅ Detailed implementation plan (WEB_TASKS.md, WEB_PLAN.md)
- ✅ Working FastAPI backend
- ✅ Working React + Tailwind frontend
- ✅ Full integration between frontend and backend
- ✅ Integration with existing Python application
- ✅ Documentation (README.md)

**To run your new web UI:**

1. Start backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   python main.py
   ```

2. Start frontend (separate terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Open browser to http://localhost:3000 (or 5173 for Vite)

4. Test thoroughly against terminal app to verify identical results
