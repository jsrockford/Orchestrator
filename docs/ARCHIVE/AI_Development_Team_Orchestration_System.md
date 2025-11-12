# AI Development Team Orchestration System

## Project Description

Build an orchestration layer on top of the existing Claude and Gemini tmux controllers that enables both AIs to collaborate as an autonomous development team. The system will facilitate structured discussions, coordinate task assignments, manage code generation, and provide human oversight mechanisms for critical decisions.

### Core Objective
Transform individual AI CLI tools into a cohesive development team capable of taking high-level project requirements and delivering working software through collaborative discussion, implementation, and testing phases.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Human Interface Layer                  │
│         (Notifications, Decisions, Monitoring)           │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Orchestration Engine                        │
│  (Phase Management, Task Assignment, Conflict Resolution)│
└────────────┬─────────────────────────┬──────────────────┘
             │                         │
┌────────────▼──────────┐  ┌──────────▼──────────────────┐
│  Conversation Manager │  │     Context Manager         │
│  (Turn-taking, Flow)  │  │  (State, History, Memory)   │
└────────────┬──────────┘  └──────────┬──────────────────┘
             │                         │
┌────────────▼─────────────────────────▼──────────────────┐
│           Existing Controller Infrastructure             │
│     (ClaudeController)          (GeminiController)       │
└──────────────────────────────────────────────────────────┘
```

## Implementation Task List

### Phase 1: Foundation (Week 1)

#### Task 1.1: Create Core Orchestrator Class
- **File**: `src/orchestrator/orchestrator.py`
- **Description**: Main orchestration engine that coordinates both AIs
```python
class DevelopmentTeamOrchestrator:
    - __init__(claude_controller, gemini_controller)
    - start_project(requirements: str)
    - get_project_status() -> dict
    - pause_team()
    - resume_team()
```

#### Task 1.2: Implement Conversation Manager
- **File**: `src/orchestrator/conversation_manager.py`
- **Description**: Manages turn-taking and conversation flow between AIs
```python
class ConversationManager:
    - facilitate_discussion(topic: str, max_turns: int) -> list
    - determine_next_speaker(context: list) -> Controller
    - detect_consensus(conversation: list) -> bool
    - detect_conflict(conversation: list) -> tuple[bool, str]
```

#### Task 1.3: Create Context Manager
- **File**: `src/orchestrator/context_manager.py`
- **Description**: Maintains project state and conversation history
```python
class ContextManager:
    - save_decision(decision: dict)
    - get_project_context() -> dict
    - build_prompt(ai_name: str, task: str, include_history: bool) -> str
    - summarize_conversation(messages: list, max_length: int) -> str
```

#### Task 1.4: Add Project State Persistence
- **File**: `src/orchestrator/state_store.py`
- **Description**: JSON-based storage for project state
```python
class StateStore:
    - save_project(project_id: str, state: dict)
    - load_project(project_id: str) -> dict
    - list_projects() -> list
    - update_progress(project_id: str, phase: str, progress: float)
```

### Phase 2: Communication Bridge (Week 2)

#### Task 2.1: Implement Message Router
- **File**: `src/orchestrator/message_router.py`
- **Description**: Routes messages between AIs based on context and rules
```python
class MessageRouter:
    - route_message(from_ai: str, message: str, context: dict) -> str
    - needs_human_intervention(message: str) -> bool
    - extract_code_blocks(message: str) -> list
    - format_for_recipient(message: str, recipient: str) -> str
```

#### Task 2.2: Create Human Decision Interface
- **File**: `src/orchestrator/human_interface.py`
- **Description**: Manages human notifications and input collection
```python
class HumanInterface:
    - notify_human(message: str, urgency: str)
    - get_human_decision(context: str, options: list) -> str
    - summarize_for_human(conversation: list) -> str
    - is_human_approval_needed(decision_type: str) -> bool
```

#### Task 2.3: Build Phase Management System
- **File**: `src/orchestrator/phase_manager.py`
- **Description**: Manages project phases and transitions
```python
class PhaseManager:
    phases = ["DISCOVERY", "DESIGN", "IMPLEMENTATION", "TESTING", "DEPLOYMENT"]
    
    - get_current_phase() -> str
    - transition_phase(from_phase: str, to_phase: str) -> bool
    - get_phase_checklist(phase: str) -> list
    - validate_phase_completion(phase: str) -> tuple[bool, list]
```

### Phase 3: Task Execution (Week 3)

#### Task 3.1: Implement Task Decomposer
- **File**: `src/orchestrator/task_manager.py`
- **Description**: Breaks down projects into executable tasks
```python
class TaskManager:
    - decompose_requirements(requirements: str) -> list
    - assign_task(task: dict) -> str  # Returns ai_name
    - track_task_progress(task_id: str, status: str)
    - handle_task_failure(task_id: str, error: str) -> dict
```

#### Task 3.2: Add Code Generation Coordinator
- **File**: `src/orchestrator/code_coordinator.py`
- **Description**: Manages code generation and file operations
```python
class CodeCoordinator:
    - request_code_generation(ai: Controller, spec: str) -> str
    - save_generated_code(filename: str, content: str)
    - request_code_review(reviewer: Controller, code: str) -> dict
    - merge_code_changes(original: str, changes: str) -> str
```

#### Task 3.3: Create Testing Orchestrator
- **File**: `src/orchestrator/test_orchestrator.py`
- **Description**: Coordinates test generation and execution
```python
class TestOrchestrator:
    - generate_test_plan(requirements: str) -> list
    - request_test_generation(ai: Controller, component: str) -> str
    - execute_tests() -> dict
    - coordinate_debugging(error: str) -> str
```

### Phase 4: Integration & Polish (Week 4)

#### Task 4.1: Build Unified CLI Interface
- **File**: `src/cli/team_cli.py`
- **Description**: Command-line interface for the orchestration system
```python
Commands:
- team start-project "requirements"
- team status
- team pause/resume
- team decide "option"
- team show-conversation
- team list-tasks
```

#### Task 4.2: Implement Monitoring Dashboard
- **File**: `src/monitoring/dashboard.py`
- **Description**: Real-time monitoring of AI team activity
```python
class Dashboard:
    - display_project_status()
    - show_active_conversations()
    - display_pending_decisions()
    - show_task_progress()
```

#### Task 4.3: Add Configuration Management
- **File**: `config_orchestrator.yaml`
- **Description**: Configuration for orchestration behavior
```yaml
orchestrator:
  max_autonomous_turns: 20
  human_approval_required_for:
    - database_design
    - api_structure
    - security_decisions
  phase_timeouts:
    discovery: 3600  # 1 hour
    implementation: 14400  # 4 hours
```

#### Task 4.4: Create Integration Tests
- **File**: `tests/test_orchestration.py`
- **Description**: End-to-end tests for orchestration system
- Test discovery phase conversation
- Test task assignment logic
- Test human intervention flow
- Test error recovery
- Test full project simulation

### Phase 5: Advanced Features (Optional)

#### Task 5.1: Add Learning System
- Track human decisions and learn patterns
- Reduce future interruptions for similar decisions

#### Task 5.2: Implement Parallel Task Execution
- Allow both AIs to work on independent tasks simultaneously
- Add merge conflict resolution

#### Task 5.3: Create Project Templates
- Pre-built patterns for common project types
- Reduce discovery phase time

## Technical Specifications

### Message Format
```python
{
    "id": "msg_001",
    "timestamp": "2024-01-10T10:30:00Z",
    "from": "claude",
    "to": "gemini",
    "phase": "DISCOVERY",
    "type": "response|question|code|decision_needed",
    "content": "message text",
    "metadata": {
        "requires_human": false,
        "confidence": 0.85
    }
}
```

### Decision Points Format
```python
{
    "id": "decision_001",
    "context": "The team needs to choose a database",
    "options": [
        {"id": "A", "description": "PostgreSQL", "proposer": "claude"},
        {"id": "B", "description": "MongoDB", "proposer": "gemini"}
    ],
    "recommendation": "A",
    "urgency": "normal|high|blocking"
}
```

## Success Criteria

1. **Basic Conversation**: System can facilitate 10+ turn conversation between AIs
2. **Human Intervention**: Human is notified within 30 seconds of decision points
3. **Task Completion**: Can complete a simple CRUD project from requirements
4. **Error Recovery**: Handles AI timeout/errors gracefully
5. **Context Preservation**: Maintains context across 1+ hour sessions
6. **Code Generation**: Produces runnable code for 3+ file project

## Dependencies

- Existing `TmuxController`, `ClaudeController`, `GeminiController`
- Existing `OutputParser` for response extraction
- Python 3.8+ with asyncio for parallel operations
- PyYAML for configuration
- Optional: Rich library for better CLI output
- Optional: SQLite for persistent state storage

## Getting Started

1. Create the `src/orchestrator/` directory
2. Start with `orchestrator.py` and `conversation_manager.py`
3. Test basic conversation flow between AIs
4. Add human intervention points
5. Iterate based on real usage patterns

The system should be built incrementally, with each phase producing a working subset of functionality that can be tested with real projects.