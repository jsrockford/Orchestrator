# Web UI Development Workflow

This directory contains instruction files for orchestrating AI-assisted web UI development using a three-phase collaborative approach. These templates guide multiple AI sessions through adding a modern web interface (FastAPI backend + React/Tailwind frontend) to an existing Python terminal/CLI application.

## Overview

This workflow extends your existing Python application with a professional web interface without modifying the core business logic. The process is divided into three phases, each with specialized AI agents working collaboratively.

### Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Tailwind CSS
- **Communication**: REST API (JSON)
- **Integration**: Direct import of existing Python functions

## The Three-Phase Workflow

```
Phase 1: Requirements (PRD)
  ↓
Phase 2: Planning (Task Breakdown)
  ↓
Phase 3: Implementation (Full-Stack Development)
```

## Phase 1: Web UI Requirements (PRD)

**Goal**: Define what the web UI needs to do and how it integrates with existing code.

**Participants**:
- Product Manager (Primary)
- UX Designer (Collaborator)

**Instruction File**: `ROLE_ProductManager_WebUI.md`

**Process**:
1. Analyze existing terminal application to understand functionality
2. Identify all input parameters and output formats
3. Define web form fields and results display
4. Specify API contract between frontend and backend
5. Document integration approach with existing Python code
6. Create comprehensive Web UI PRD

**Input Required**:
- `EXISTING_APP_ANALYSIS.md` - Description/analysis of current Python app
- `USER_REQUEST.md` - Stakeholder description of web UI needs
- Existing Python code (for reference)

**Output Produced**:
- `WEB_PRD.md` - Complete Web UI requirements document

**When to Request Clarification**:
- Ambiguous output format requirements
- Unclear which features from terminal app should be in web UI
- Missing information about input validation rules
- Uncertainty about deployment requirements

## Phase 2: Web UI Planning (Task Breakdown)

**Goal**: Break down the PRD into actionable development tasks organized by workstream.

**Participants**:
- Engineering Manager (Primary)
- Full Stack Architect (Collaborator)

**Instruction File**: `ROLE_EngineeringManager_WebUI.md`

**Process**:
1. Review Web UI PRD thoroughly
2. Break down into tasks organized by workstream:
   - **Setup**: Environment configuration, project initialization
   - **Backend**: FastAPI API development, integration with existing code
   - **Frontend**: React components, Tailwind styling, form logic
   - **Integration**: Connect frontend to backend, E2E testing
3. Identify dependencies (what must be done first)
4. Identify parallel opportunities (backend and frontend can develop simultaneously)
5. Define milestones and estimate timeline
6. Create implementation plan

**Input Required**:
- `WEB_PRD.md` - From Phase 1
- `EXISTING_APP_ANALYSIS.md` - Understanding of existing code

**Output Produced**:
- `WEB_TASKS.md` - Detailed task breakdown with dependencies
- `WEB_PLAN.md` - Implementation plan with milestones and timeline

**Key Considerations**:
- Backend and frontend tasks should be clearly separated
- Most backend and frontend work can happen in parallel
- Integration requires both workstreams to be functional
- Don't forget setup, testing, and deployment tasks

## Phase 3: Web UI Implementation

**Goal**: Build the complete web interface - backend, frontend, and integration.

**Participants**:
- Full Stack Developer (Primary)
- Code Reviewer (Collaborator)
- QA Engineer (Supports testing)

**Instruction File**: `ROLE_FullStackDeveloper_WebUI.md`

**Process**:
1. **Setup Phase** (Parallel):
   - Initialize FastAPI backend project
   - Initialize React + Tailwind frontend project
   - Configure development environments
   - Setup CORS and communication

2. **Backend Development**:
   - Create Pydantic models for API validation
   - Implement API endpoints
   - Integrate with existing Python functions
   - Add error handling
   - Test API with Postman/curl

3. **Frontend Development** (Can be parallel with backend):
   - Create React components (InputForm, Results, etc.)
   - Implement form validation
   - Style with Tailwind CSS
   - Ensure mobile responsiveness
   - Test components with mock data

4. **Integration**:
   - Connect React frontend to FastAPI backend
   - Implement API client
   - Handle loading and error states
   - Display results from backend
   - Test complete user flow

5. **Testing & Validation**:
   - Verify results match terminal app exactly
   - Test all edge cases
   - Test on multiple browsers
   - Test mobile responsiveness
   - Fix bugs

**Input Required**:
- `WEB_PRD.md` - Requirements
- `WEB_TASKS.md` - Task breakdown
- `WEB_PLAN.md` - Implementation plan
- Existing Python application code

**Output Produced**:
- `backend/` - Complete FastAPI backend
- `frontend/` - Complete React frontend
- `README.md` - Setup and usage instructions
- Test files and documentation

**Critical Success Factors**:
- DO NOT modify existing Python business logic
- MUST configure CORS properly
- MUST maintain decimal precision in calculations
- MUST verify results match terminal app
- MUST handle all error cases gracefully

## File Structure After Completion

```
your-project/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── api/
│   │   └── routes.py          # API endpoints
│   ├── models/
│   │   └── schemas.py         # Pydantic models
│   ├── requirements.txt       # Backend dependencies
│   └── tests/
│       └── test_api.py        # Backend tests
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx            # Main app
│   │   ├── components/        # React components
│   │   └── api/
│   │       └── client.js      # API communication
│   ├── package.json
│   └── tailwind.config.js
│
├── calculator.py               # EXISTING CODE (unchanged)
├── WEB_PRD.md                 # Requirements document
├── WEB_TASKS.md               # Task breakdown
├── WEB_PLAN.md                # Implementation plan
└── README.md                  # Project documentation
```

## Usage Instructions

### For Orchestrator System

1. **Phase 1 - Requirements**:
   ```
   Session 1: Load ROLE_ProductManager_WebUI.md
   Session 2: Load ROLE_UXDesigner_WebUI.md (if you have this role file)

   Provide: EXISTING_APP_ANALYSIS.md, USER_REQUEST.md
   Run discussion until: [[PROJECT_COMPLETE]] signal
   Collect: WEB_PRD.md
   ```

2. **Phase 2 - Planning**:
   ```
   Session 1: Load ROLE_EngineeringManager_WebUI.md
   Session 2: Load ROLE_FullStackArchitect_WebUI.md (if you have this role file)

   Provide: WEB_PRD.md, EXISTING_APP_ANALYSIS.md
   Run discussion until: [[PROJECT_COMPLETE]] signal
   Collect: WEB_TASKS.md, WEB_PLAN.md
   ```

3. **Phase 3 - Implementation**:
   ```
   Session 1: Load ROLE_FullStackDeveloper_WebUI.md
   Session 2: Load ROLE_CodeReviewer_WebUI.md (if you have this role file)

   Provide: WEB_PRD.md, WEB_TASKS.md, WEB_PLAN.md
   Run discussion until: [[PROJECT_COMPLETE]] signal
   Collect: backend/, frontend/, README.md
   ```

### For Manual Use (Single Claude Session)

If running manually in a single Claude Code session:

1. **Create your initial documents**:
   - Write `EXISTING_APP_ANALYSIS.md` describing your current Python app
   - Write `USER_REQUEST.md` with your web UI requirements

2. **Run Phase 1**:
   - Copy `ROLE_ProductManager_WebUI.md` to your project
   - Tell Claude: "Act according to ROLE_ProductManager_WebUI.md and create the Web UI PRD"
   - Review and iterate until complete
   - Save the resulting `WEB_PRD.md`

3. **Run Phase 2**:
   - Copy `ROLE_EngineeringManager_WebUI.md` to your project
   - Tell Claude: "Act according to ROLE_EngineeringManager_WebUI.md and create the implementation plan"
   - Review and iterate until complete
   - Save `WEB_TASKS.md` and `WEB_PLAN.md`

4. **Run Phase 3**:
   - Copy `ROLE_FullStackDeveloper_WebUI.md` to your project
   - Tell Claude: "Act according to ROLE_FullStackDeveloper_WebUI.md and implement the web UI"
   - Follow the tasks from WEB_TASKS.md
   - Claude will create backend and frontend code
   - Test thoroughly

## Key Features

### 🎯 Clean Integration
- Existing Python code remains **unchanged**
- Backend imports existing functions directly
- No refactoring of business logic required

### 🎨 Modern UI
- React + Tailwind CSS for professional appearance
- Mobile-responsive design out of the box
- Loading states, error handling, success feedback
- Clean, intuitive user interface

### ⚡ FastAPI Backend
- Automatic API documentation (Swagger UI)
- Fast, modern Python framework
- Pydantic validation for type safety
- Easy to deploy and scale

### ✅ Complete Testing
- Backend API tests
- Frontend component tests
- Integration/E2E tests
- Verification against terminal app results

### 📱 Responsive Design
- Works on desktop, tablet, and mobile
- Tailwind CSS for consistent styling
- Modern, accessible interface

## Common Issues and Solutions

### Issue: CORS Errors
**Symptom**: Frontend can't connect to backend, browser console shows CORS error
**Solution**: Ensure FastAPI CORS middleware is configured with correct frontend URL
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Results Don't Match Terminal App
**Symptom**: Web UI calculations differ from terminal app
**Solution**:
- Check data type conversions (Decimal vs float)
- Verify percentage conversions (18.5% → 0.185)
- Ensure same rounding/precision rules
- Test with exact same inputs side-by-side

### Issue: Import Errors (Backend can't import existing code)
**Symptom**: `ImportError: cannot import name 'calculate_scenario_a'`
**Solution**:
- Verify path to existing Python file
- Add parent directory to sys.path if needed
- Check function names match exactly
- Ensure existing code is in Python path

### Issue: Mobile Layout Breaks
**Symptom**: UI doesn't look good on mobile devices
**Solution**:
- Use Tailwind responsive classes (`md:`, `lg:`)
- Test with browser dev tools mobile view
- Stack form inputs vertically on mobile
- Ensure results display properly in narrow width

## Customization

These instruction files are designed to be flexible. You can customize:

1. **Technology Stack**:
   - Replace FastAPI with Flask/Django if preferred
   - Replace React with Vue/Svelte if preferred
   - Replace Tailwind with Bootstrap/Material-UI

2. **Features**:
   - Add authentication if needed
   - Add data persistence (database)
   - Add visualization/charts
   - Add PDF export

3. **Deployment**:
   - Deploy to Vercel/Netlify (frontend)
   - Deploy to Heroku/Railway (backend)
   - Containerize with Docker
   - Deploy as single server with static file serving

## Best Practices

1. **Keep Existing Code Separate**: Never modify working terminal app code
2. **Test Early and Often**: Test backend before frontend integration
3. **Mobile First**: Design for mobile from the start
4. **Error Handling**: Handle all error cases gracefully
5. **Validation**: Validate on both client and server side
6. **Documentation**: Keep README updated with setup instructions
7. **Decimal Precision**: Always use Decimal for financial calculations
8. **Environment Variables**: Use .env files for configuration

## Example: Credit Card Calculator

The instruction files use a credit card balance transfer calculator as the example application throughout. This example:

- Accepts multiple input parameters (debt, APR, payment, etc.)
- Performs financial calculations with decimal precision
- Returns comparison between two scenarios
- Provides a recommendation

Your application may be different, but the same principles apply:
1. Identify all inputs from terminal app
2. Map them to web form fields
3. Create API to call existing functions
4. Display results in clean UI

## Support and Troubleshooting

When issues arise:

1. **Check the instruction files**: They contain detailed guidance and examples
2. **Review the PRD**: Ensure requirements are clear and complete
3. **Test each layer**: Backend, frontend, integration separately
4. **Verify against terminal app**: Results must match exactly
5. **Check browser console**: For frontend JavaScript errors
6. **Check backend logs**: For API errors and exceptions

## License and Usage

These instruction files are part of the Orchestrator project and are designed to facilitate AI-assisted development workflows. Feel free to adapt them to your specific needs and technology preferences.

---

**Need help?** See `SESSION_MAPPING.md` for detailed session configuration examples.
