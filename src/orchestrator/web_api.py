"""FastAPI application exposing orchestrator control and monitoring endpoints."""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Sequence, Type, cast

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..controllers import ClaudeController, CodexController, GeminiController, QwenController
from ..controllers.session_backend import SessionBackendError, SessionNotFoundError
from ..utils.exceptions import SessionAlreadyExists
from ..utils.logger import get_logger
from ..utils.config_loader import get_config

if TYPE_CHECKING:
    from .orchestrator import DevelopmentTeamOrchestrator

logger = get_logger("orchestrator.web_api")


# Phase 4: HitL - WebSocket connection manager for broadcasting events
class DiscussionEventManager:
    """
    Manages WebSocket connections for discussion events.

    Allows broadcasting human turn events and other discussion state changes
    to all connected clients in real-time.
    """

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self.logger = get_logger("orchestrator.web_api.events")

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.debug("WebSocket connected for discussion events (total: %d)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from active list."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.logger.debug("WebSocket disconnected from discussion events (total: %d)", len(self.active_connections))

    async def broadcast(self, event: Dict[str, Any]) -> None:
        """
        Send an event to all connected clients.

        Args:
            event: Event payload dictionary (must include 'type' field)
        """
        if not self.active_connections:
            return

        self.logger.debug("Broadcasting event type='%s' to %d clients", event.get("type"), len(self.active_connections))

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(event)
            except (WebSocketDisconnect, RuntimeError) as exc:
                self.logger.debug("Failed to send to connection: %s", exc)
                disconnected.append(connection)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Unexpected error broadcasting to connection: %s", exc)
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global event manager instance
discussion_event_manager = DiscussionEventManager()


def broadcast_event_sync(event: Dict[str, Any]) -> None:
    """
    Broadcast an event from synchronous code (conversation manager).

    This creates a new event loop in a thread-safe way to send the event.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, schedule as a task
            asyncio.create_task(discussion_event_manager.broadcast(event))
        else:
            # If no loop is running, run it synchronously
            loop.run_until_complete(discussion_event_manager.broadcast(event))
    except RuntimeError:
        # No event loop, create a temporary one
        asyncio.run(discussion_event_manager.broadcast(event))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to broadcast event from sync context: %s", exc)


# Pydantic models for request/response bodies
class InstructionFile(BaseModel):
    """Request body for saving instruction files."""
    content: str
    project_directory: Optional[str] = None


class DirectoryPath(BaseModel):
    """Request body for filesystem browsing."""
    path: str


class NewFolder(BaseModel):
    """Request body for creating new folders."""
    path: str
    folderName: str


class StartSessionsRequest(BaseModel):
    """Payload describing which sessions to start and where."""
    project_directory: str
    models: Optional[Sequence[str]] = None


class StopSessionsRequest(BaseModel):
    """Payload describing which sessions to stop."""
    models: Optional[Sequence[str]] = None


class PromptRequest(BaseModel):
    """Request body for sending prompts to AI models."""
    prompt: str
    models: list[str]
    submit: bool = True


class DiscussionConfig(BaseModel):
    """Configuration payload for orchestrated discussions."""
    max_turns: int = 10
    starting_model: Optional[str] = None
    participants: Optional[Sequence[str]] = None
    discussion_topic: Optional[str] = None
    include_history: bool = True
    log_level: Optional[str] = None


class ExtendDiscussionRequest(BaseModel):
    """Payload for extending an in-flight discussion's turn budget."""
    extend_by: int = Field(..., ge=1, description="Number of additional turns to allow")


class HumanSubmitRequest(BaseModel):
    """Payload for human participant submitting their turn response."""
    response: str = Field(..., description="Human's response text")


class ModelSettingsUpdate(BaseModel):
    """Request body for updating per-model overrides."""
    project_directory: str
    overrides: Dict[str, Any] = Field(default_factory=dict)


# Mapping of model names to their instruction files
INSTRUCTION_FILES = {
    "Claude": "CLAUDE.md",
    "Codex": "AGENTS.md",
    "Gemini": "GEMINI.md",
    "Qwen": "QWEN.md",
}

CONTROLLER_FACTORIES: Dict[str, Type[Any]] = {
    "claude": ClaudeController,
    "codex": CodexController,
    "gemini": GeminiController,
    "qwen": QwenController,
}

MODEL_SETTING_FIELDS: List[Dict[str, Any]] = [
    {
        "key": "pane_width",
        "label": "Pane Width (columns)",
        "description": "Width of the tmux pane allocated to the model session.",
        "type": "number",
        "value_type": "int",
        "min": 80,
        "max": 400,
        "step": 5,
    },
    {
        "key": "pane_height",
        "label": "Pane Height (rows)",
        "description": "Height of the tmux pane allocated to the model session.",
        "type": "number",
        "value_type": "int",
        "min": 20,
        "max": 120,
        "step": 1,
        "fallback_default": 50,
    },
    {
        "key": "startup_timeout",
        "label": "Startup Timeout (seconds)",
        "description": "Maximum time to wait for the CLI to finish booting.",
        "type": "number",
        "value_type": "float",
        "min": 5,
        "max": 900,
        "step": 1,
    },
    {
        "key": "response_timeout",
        "label": "Response Timeout (seconds)",
        "description": "Maximum time to wait for a command response before aborting.",
        "type": "number",
        "value_type": "float",
        "min": 30,
        "max": 3600,
        "step": 5,
    },
    {
        "key": "ready_check_interval",
        "label": "Ready Check Interval (seconds)",
        "description": "Delay between consecutive ready-state sampling passes.",
        "type": "number",
        "value_type": "float",
        "min": 0.1,
        "max": 5.0,
        "step": 0.1,
    },
    {
        "key": "ready_stable_checks",
        "label": "Ready Stable Checks",
        "description": "Number of consecutive calm samples required before sending the next command.",
        "type": "number",
        "value_type": "int",
        "min": 1,
        "max": 10,
        "step": 1,
    },
    {
        "key": "ready_stabilization_delay",
        "label": "Ready Stabilization Delay (seconds)",
        "description": "Extra delay after ready indicators before injecting the first command.",
        "type": "number",
        "value_type": "float",
        "min": 0.0,
        "max": 5.0,
        "step": 0.1,
    },
    {
        "key": "text_enter_delay",
        "label": "Text Enter Delay (seconds)",
        "description": "Delay between pasting text and submitting it.",
        "type": "number",
        "value_type": "float",
        "min": 0.0,
        "max": 2.0,
        "step": 0.1,
    },
    {
        "key": "post_text_delay",
        "label": "Post Text Delay (seconds)",
        "description": "Additional pause after sending text before continuing.",
        "type": "number",
        "value_type": "float",
        "min": 0.0,
        "max": 2.0,
        "step": 0.1,
        "fallback_default": 0.0,
    },
    {
        "key": "debug_wait_logging",
        "label": "Debug Wait Logging",
        "description": "Enable verbose logging for wait-for-ready loops.",
        "type": "boolean",
        "value_type": "boolean",
        "fallback_default": False,
    },
    {
        "key": "pause_on_manual_clients",
        "label": "Pause On Manual Clients",
        "description": "Automatically pause automation when you attach to the tmux session.",
        "type": "boolean",
        "value_type": "boolean",
        "fallback_default": False,
    },
    {
        "key": "tool_timeout",
        "label": "Tool Timeout (seconds)",
        "description": "Maximum time Gemini tools are allowed to run before aborting.",
        "type": "number",
        "value_type": "float",
        "min": 5,
        "max": 120,
        "step": 1,
        "models": ["gemini"],
    },
]

MODEL_SETTING_FIELD_MAP: Dict[str, Dict[str, Any]] = {
    field["key"]: field for field in MODEL_SETTING_FIELDS
}


def iter_model_setting_fields(model_key: str) -> List[Dict[str, Any]]:
    """Return the subset of fields applicable to the requested model."""
    selected: List[Dict[str, Any]] = []
    for field in MODEL_SETTING_FIELDS:
        models = field.get("models")
        if models and model_key not in models:
            continue
        selected.append(field)
    return selected


def convert_setting_value(field_meta: Dict[str, Any], raw_value: Any, *, allow_none: bool) -> Any:
    """Convert the incoming value to the expected Python type."""
    if raw_value is None:
        if allow_none:
            return None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value for '{field_meta['key']}' is required",
        )

    value_type = field_meta.get("value_type", "float")
    try:
        if value_type == "boolean":
            if isinstance(raw_value, bool):
                value = raw_value
            elif isinstance(raw_value, str):
                normalized = raw_value.strip().lower()
                if normalized in {"true", "1", "yes", "on"}:
                    value = True
                elif normalized in {"false", "0", "no", "off"}:
                    value = False
                else:
                    raise ValueError(raw_value)
            elif isinstance(raw_value, (int, float)):
                value = bool(raw_value)
            else:
                raise ValueError(raw_value)
        elif value_type == "int":
            value = int(float(raw_value))
        elif value_type == "float":
            value = float(raw_value)
        else:
            value = str(raw_value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid value for '{field_meta['key']}': {raw_value!r}",
        ) from None

    min_value = field_meta.get("min")
    max_value = field_meta.get("max")
    if (
        isinstance(value, (int, float))
        and min_value is not None
        and value < min_value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value for '{field_meta['key']}' must be >= {min_value}",
        )
    if (
        isinstance(value, (int, float))
        and max_value is not None
        and value > max_value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value for '{field_meta['key']}' must be <= {max_value}",
        )

    return value


def get_field_default_value(field_meta: Dict[str, Any], config_section: Dict[str, Any]) -> Any:
    """Derive the baseline default for a field from the config or fallback."""
    raw_default = config_section.get(field_meta["key"])
    if raw_default is None and "fallback_default" in field_meta:
        raw_default = field_meta["fallback_default"]
    if raw_default is None:
        return None
    return convert_setting_value(field_meta, raw_default, allow_none=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for graceful startup and shutdown.

    This ensures WebSocket tasks and other async resources are properly
    cleaned up when the server shuts down, preventing "Event loop is closed"
    errors and pending task warnings.
    """
    # Startup
    logger.info("FastAPI application starting up")
    yield
    # Shutdown
    logger.info("FastAPI application shutting down, cancelling pending tasks")

    # Cancel all pending tasks gracefully
    tasks = [task for task in asyncio.all_tasks() if not task.done()]
    if tasks:
        logger.debug("Cancelling %d pending tasks during shutdown", len(tasks))
        for task in tasks:
            task.cancel()

        # Wait for tasks to complete cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("FastAPI shutdown complete")


def create_app(orchestrator: "DevelopmentTeamOrchestrator") -> FastAPI:
    """
    Build a FastAPI application bound to the provided orchestrator instance.

    Args:
        orchestrator: Live orchestrator instance used to satisfy API requests.
    """

    app = FastAPI(
        title="Development Team Orchestrator API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.orchestrator = orchestrator

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    async def health() -> Dict[str, str]:
        """Return a simple heartbeat payload for readiness probes."""
        return {"status": "ok"}

    register_control_routes(app)
    register_discussion_routes(app)
    register_instruction_routes(app)
    register_settings_routes(app)
    register_filesystem_routes(app)
    register_stream_routes(app)

    return app


def get_orchestrator(request: Request) -> "DevelopmentTeamOrchestrator":
    """Dependency that returns the orchestrator stored on the FastAPI app."""
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator is not available",
        )
    return orchestrator


def validate_model_name(orchestrator: "DevelopmentTeamOrchestrator", model_name: str) -> None:
    """Raise 404 if the model is not registered."""
    if model_name not in orchestrator.controllers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown model '{model_name}'",
        )


ALLOWED_KEYS: Dict[str, Iterable[str]] = {
    "Up": ("Up", "ArrowUp"),
    "Down": ("Down", "ArrowDown"),
    "Enter": ("Enter", "Return"),
    "Escape": ("Escape", "Esc"),
}


def normalize_key_name(key_name: str) -> str:
    """Normalize user-provided key names to control channel tokens."""
    candidate = key_name.strip()
    for normalized, variants in ALLOWED_KEYS.items():
        if candidate == normalized or candidate in variants:
            return normalized
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported key '{key_name}'",
    )


def normalize_model_names(models: Sequence[str]) -> List[str]:
    """
    Normalize and validate requested model identifiers.

    Phase 3: HitL - Allows 'human' as a special participant type alongside AI models.
    """
    if not models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one model must be specified",
        )

    normalized: List[str] = []
    seen = set()
    for raw in models:
        if raw is None:
            candidate = ""
        else:
            candidate = str(raw).strip().lower()

        if not candidate:
            continue

        # Phase 3: HitL - Allow 'human' as a valid participant
        if candidate == "human":
            if candidate not in seen:
                normalized.append(candidate)
                seen.add(candidate)
            continue

        if candidate not in CONTROLLER_FACTORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown model '{raw}'. Supported models: {', '.join(sorted(CONTROLLER_FACTORIES))}, human",
            )

        if candidate not in seen:
            normalized.append(candidate)
            seen.add(candidate)

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid models were provided",
        )

    return normalized


def normalize_single_model_name(model_name: str) -> str:
    """Normalize a single model identifier."""
    result = normalize_model_names([model_name])
    return result[0]


def resolve_project_directory(path_str: str) -> Path:
    """Resolve and validate the requested project directory."""
    if not path_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_directory is required",
        )

    try:
        path = Path(path_str).expanduser().resolve()
    except OSError as exc:  # pragma: no cover - filesystem-dependent
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid project directory: {exc}",
        ) from exc

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project directory '{path}' does not exist",
        )
    if not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project directory '{path}' is not a directory",
        )

    return path


SECURITY_MARKER = "<!-- SECURITY_BOUNDARY_MARKER: DO NOT REMOVE -->"
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "ALL_MODELS_TEMPLATE.md"


def get_instruction_template(project_dir: str) -> str:
    """
    Load the instruction template and substitute the project directory.

    Args:
        project_dir: The project directory path to substitute into the template

    Returns:
        The template content with project_dir substituted
    """
    try:
        logger.info("Looking for template at: %s", TEMPLATE_PATH)
        logger.info("Template exists: %s", TEMPLATE_PATH.exists())
        if not TEMPLATE_PATH.exists():
            logger.warning("Template file not found at %s, using fallback", TEMPLATE_PATH)
            # Fallback with full instructions if template doesn't exist
            return f"""{SECURITY_MARKER}
## CRITICAL: Project Directory Security

**Your working directory**: {project_dir}

**YOU MUST**:
- Only create, modify, or delete files within: {project_dir}
- Use relative paths (./file.txt) or absolute paths starting with {project_dir}
- If asked to work outside this directory, politely decline and explain the restriction

**FORBIDDEN PATHS**:
- /etc/ (system configuration)
- /home/other_user/ (other users' files)
- ../../ (parent directory traversal)
- /tmp/ (temporary system files)
- Any path outside your working directory

**Example**:
✅ ALLOWED: `./src/main.py`, `docs/README.md`, `{project_dir}/config.json`
❌ FORBIDDEN: `/etc/passwd`, `../../other_project/`, `/home/dgray/Projects/Orchestrator/`

{SECURITY_MARKER}

═══════════════════════════════════════════════════════════
⚠️  CRITICAL REQUIREMENTS - READ FIRST ⚠️
═══════════════════════════════════════════════════════════

## 1. RESPONSE DELIMITER PROTOCOL (MANDATORY)

When responding to your teammates, you MUST wrap your final
response in delimiters. NO EXCEPTIONS.

**FORMAT:**
```
**[[RESPONSE_START]]**
Your actual response here
**[[RESPONSE_END]]**
```

**Why this matters:**
- Everything outside these delimiters (thinking, tool use, file
  edits, etc.) will be filtered out and NOT sent to your teammate
- Missing delimiters = BROKEN COMMUNICATION
- Your teammate will only see what's inside the delimiters

**Example:**
```
[Your internal reasoning and tool usage here...]

**[[RESPONSE_START]]**
I've reviewed the code and found the following issues:
1. The collision detection needs adjustment
2. Please update line 42 to fix the boundary check
**[[RESPONSE_END]]**
```

## 2. PROJECT COMPLETION SIGNAL

When ALL project objectives are met and you AND your teammates
agree the work is complete, signal completion by including:

**[[PROJECT_COMPLETE]]**

Place this INSIDE your **[[RESPONSE_START]]** delimiters.

The orchestrator requires 66% consensus to end the discussion.
Only signal when you genuinely believe the project is done.

 =============================================================

"""

        template_content = TEMPLATE_PATH.read_text(encoding='utf-8')

        # Replace the placeholder project directory with the actual one
        # The template has a hardcoded path that we need to replace
        template_content = template_content.replace(
            '/home/dgray/Projects/scratch/project-orch2',
            project_dir
        )

        return template_content

    except Exception as exc:
        logger.error("Failed to load template from %s: %s", TEMPLATE_PATH, exc)
        # Return minimal security warning as fallback
        return f"""{SECURITY_MARKER}
## CRITICAL: Project Directory Security

**Your working directory**: {project_dir}

{SECURITY_MARKER}

"""


def ensure_instruction_file_security(project_dir: Path, model_name: str) -> None:
    """
    Ensure instruction file exists with template content (security + protocol) in the project directory.

    Args:
        project_dir: The project directory path
        model_name: The model name (e.g., "claude", "gemini")
    """
    instruction_file = INSTRUCTION_FILES.get(model_name.capitalize())
    if not instruction_file:
        logger.warning("No instruction file mapping for model '%s'", model_name)
        return

    file_path = project_dir / instruction_file
    template_content = get_instruction_template(str(project_dir))

    try:
        if file_path.exists():
            # Read existing content
            content = file_path.read_text(encoding='utf-8')

            # Check if security marker already present
            if SECURITY_MARKER in content:
                logger.debug("Template content already present in %s", file_path)
                return

            # Prepend template content (security + protocol)
            new_content = template_content + "\n" + content
            file_path.write_text(new_content, encoding='utf-8')
            logger.info("Prepended instruction template to existing %s", file_path)
        else:
            # Create new file with template content
            file_path.write_text(template_content, encoding='utf-8')
            logger.info("Created new instruction file %s with template content", file_path)

    except Exception as exc:
        logger.error("Failed to update instruction file %s: %s", file_path, exc)
        # Don't raise - this is not critical enough to fail session startup


def controller_session_active(controller: Any) -> bool:
    """Return True if the controller reports an active session."""
    exists_fn = getattr(controller, "session_exists", None)
    if not callable(exists_fn):
        return False
    try:
        return bool(exists_fn())
    except Exception:  # noqa: BLE001
        return False


def kill_controller_session(controller: Any) -> None:
    """Invoke the most appropriate kill method on the controller."""
    kill_fn = getattr(controller, "kill_session", None)
    if callable(kill_fn):
        kill_fn()
        return

    legacy_kill = getattr(controller, "kill", None)
    if callable(legacy_kill):
        legacy_kill()
        return

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Controller does not support kill_session()",
    )


def register_control_routes(app: FastAPI) -> None:
    """Attach control endpoints to the provided FastAPI app."""

    @app.post("/api/control/pause", tags=["control"])
    async def pause(orchestrator: "DevelopmentTeamOrchestrator" = Depends(get_orchestrator)) -> Dict[str, Any]:
        controllers = orchestrator.controllers
        if not controllers:
            return {"status": "paused", "controllers": []}

        for name, controller in controllers.items():
            pause_fn = getattr(controller, "pause_automation", None)
            if not callable(pause_fn):
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail=f"Controller '{name}' does not support pause_automation()",
                )
            pause_fn("api-request")

        # If a discussion is running, pause it so human can inject prompts
        if orchestrator.discussion_state == "RUNNING":
            orchestrator.discussion_state = "PAUSED"
            logger.info("Discussion paused for human interjection")

        return {"status": "paused", "controllers": list(controllers.keys()), "discussion_state": orchestrator.discussion_state}

    @app.post("/api/control/resume", tags=["control"])
    async def resume(orchestrator: "DevelopmentTeamOrchestrator" = Depends(get_orchestrator)) -> Dict[str, Any]:
        controllers = orchestrator.controllers
        if not controllers:
            return {"status": "resumed", "controllers": []}

        for name, controller in controllers.items():
            resume_fn = getattr(controller, "resume_automation", None)
            if not callable(resume_fn):
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail=f"Controller '{name}' does not support resume_automation()",
                )
            resume_fn()

        # If a discussion was paused, resume it
        if orchestrator.discussion_state == "PAUSED":
            orchestrator.discussion_state = "RUNNING"
            # Also clear human_control_mode in the conversation manager
            manager = getattr(orchestrator, "discussion_manager", None)
            if manager is not None:
                if hasattr(manager, "human_control_mode"):
                    manager.human_control_mode = False
                    logger.debug("Cleared human_control_mode in conversation manager")
            logger.info("Discussion resumed after human interjection")

        return {"status": "resumed", "controllers": list(controllers.keys()), "discussion_state": orchestrator.discussion_state}

    @app.post("/api/control/{model_name}/key/{key_name}", tags=["control"])
    async def send_key(
        model_name: str,
        key_name: str,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, str]:
        validate_model_name(orchestrator, model_name)
        normalized = normalize_key_name(key_name)
        controller = orchestrator.controllers[model_name]

        manager = getattr(orchestrator, "discussion_manager", None)
        discussion_state = getattr(orchestrator, "discussion_state", "IDLE")
        if manager is not None and discussion_state in {"RUNNING", "PAUSED"}:
            process_key = getattr(manager, "process_key_command", None)
            if callable(process_key):
                try:
                    success = process_key(model_name, [normalized])
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Failed to route key '%s' to %s via discussion manager: %s",
                        normalized,
                        model_name,
                        exc,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to send key: {exc}",
                    ) from exc

                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to send key via discussion manager",
                    )

                return {"status": "sent", "model": model_name, "key": normalized}

        send_key_fn = getattr(controller, "send_key", None)
        if not callable(send_key_fn):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"Controller '{model_name}' does not support send_key()",
            )

        try:
            send_key_fn(normalized)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to send key '%s' to %s: %s", normalized, model_name, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send key: {exc}",
            ) from exc

        return {"status": "sent", "model": model_name, "key": normalized}

    @app.post("/api/control/send-prompt", tags=["control"])
    async def send_prompt(
        request: PromptRequest,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        """
        Send a prompt to one or more AI models.

        Returns a dict with per-model results indicating success/failure.
        """
        manager = getattr(orchestrator, "discussion_manager", None)
        discussion_state = getattr(orchestrator, "discussion_state", "IDLE")
        if manager is not None and discussion_state in {"RUNNING", "PAUSED"}:
            if discussion_state != "PAUSED":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Pause the discussion before sending manual prompts",
                )

            try:
                manager.inject_message(
                    "human",
                    request.prompt,
                    metadata={"targets": list(request.models or [])},
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to inject discussion prompt: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to inject prompt: {exc}",
                ) from exc

            return {
                "results": {
                    "discussion": {
                        "success": True,
                        "injected": True,
                        "targets": list(request.models or []),
                    }
                }
            }

        results = {}

        for model_name in request.models:
            model_lower = model_name.lower()

            # Check if model is registered
            if model_lower not in orchestrator.controllers:
                results[model_name] = {
                    "success": False,
                    "error": "Model not running or not registered"
                }
                continue

            # Try to dispatch the command
            try:
                dispatch_result = orchestrator.dispatch_command(
                    model_lower,
                    request.prompt,
                    submit=request.submit
                )
                results[model_name] = {
                    "success": True,
                    "dispatched": dispatch_result.get("dispatched", False),
                    "queued": dispatch_result.get("queued", False),
                    "reason": dispatch_result.get("reason"),
                }
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to send prompt to %s: %s", model_name, exc)
                results[model_name] = {
                    "success": False,
                    "error": str(exc)
                }

        return {"results": results}

    @app.get("/api/control/status", tags=["control"])
    async def control_status(orchestrator=Depends(get_orchestrator)) -> Dict[str, Any]:
        controller_statuses = {
            name: orchestrator.get_controller_status(name)
            for name in orchestrator.controllers.keys()
        }
        pending = {
            name: orchestrator.get_pending_command_count(name)
            for name in orchestrator.controllers.keys()
        }
        return {
            "controllers": controller_statuses,
            "pending": pending,
            "api": {
                "running": orchestrator.api_server_running(),
                "host": orchestrator.api_host,
                "port": orchestrator.api_port,
            },
        }

    @app.post("/api/control/start-sessions", tags=["control"])
    async def start_sessions(
        payload: StartSessionsRequest,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        project_dir = resolve_project_directory(payload.project_directory)
        requested = normalize_model_names(
            list(payload.models) if payload.models is not None else list(CONTROLLER_FACTORIES.keys())
        )

        started: List[str] = []
        already_running: List[str] = []
        failed: List[Dict[str, str]] = []

        for model_name in requested:
            # Phase 3: HitL - Special handling for human participant
            if model_name == "human":
                # Human doesn't need a controller; register with None
                orchestrator.register_controller(
                    "human",
                    None,  # type: ignore
                    metadata={"type": "human", "has_controller": False},
                )
                started.append("human")
                logger.info("Registered human participant (no controller)")
                continue

            existing = orchestrator.controllers.get(model_name)
            if existing and controller_session_active(existing):
                already_running.append(model_name)
                continue
            if existing:
                orchestrator.unregister_controller(model_name)

            factory = CONTROLLER_FACTORIES.get(model_name)
            if factory is None:  # pragma: no cover - normalized inputs guard this
                failed.append({"model": model_name, "error": "Model not supported"})
                continue

            try:
                overrides = orchestrator.get_model_config_overrides(project_dir, model_name)
                controller = factory(
                    working_dir=str(project_dir),
                    config_overrides=overrides or None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to initialize controller '%s': %s", model_name, exc)
                failed.append({"model": model_name, "error": str(exc)})
                continue

            orchestrator.register_controller(
                model_name,
                controller,
                metadata={"working_dir": str(project_dir)},
            )

            start_fn = getattr(controller, "start_session", None)
            wait_fn = getattr(controller, "wait_for_ready", None)
            if not callable(start_fn):
                orchestrator.unregister_controller(model_name)
                failed.append({"model": model_name, "error": "Controller does not support start_session()"})
                continue

            try:
                # Ensure instruction file has security warnings
                ensure_instruction_file_security(project_dir, model_name)

                start_fn()
                if callable(wait_fn):
                    wait_fn()
                started.append(model_name)
            except SessionAlreadyExists as exc:
                logger.info("Session for '%s' already running: %s", model_name, exc)
                already_running.append(model_name)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to start session for '%s': %s", model_name, exc)
                failure_entry = {"model": model_name, "error": str(exc)}
                failed.append(failure_entry)
                try:
                    kill_controller_session(controller)
                except HTTPException as kill_exc:
                    failure_entry["error"] = f"{failure_entry['error']} (cleanup_failed: {kill_exc.detail})"
                except Exception as kill_exc:  # noqa: BLE001
                    logger.warning("Cleanup failed for '%s': %s", model_name, kill_exc)
                orchestrator.unregister_controller(model_name)

        if started or already_running:
            orchestrator.active_project_directory = str(project_dir)
            orchestrator.project_state = "OPEN"
        else:
            orchestrator.project_state = "IDLE"

        return {
            "success": not failed,
            "started": started,
            "already_running": already_running,
            "failed": failed,
            "project_directory": str(project_dir),
        }

    @app.post("/api/control/stop-sessions", tags=["control"])
    async def stop_sessions(
        payload: StopSessionsRequest,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        if payload.models:
            requested = normalize_model_names(list(payload.models))
        else:
            requested = list(orchestrator.controllers.keys())

        stopped: List[str] = []
        already_stopped: List[str] = []
        failed: List[Dict[str, str]] = []

        for model_name in requested:
            controller = orchestrator.controllers.get(model_name)
            if controller is None:
                already_stopped.append(model_name)
                continue

            try:
                kill_controller_session(controller)
                orchestrator.unregister_controller(model_name)
                stopped.append(model_name)
            except SessionNotFoundError:
                orchestrator.unregister_controller(model_name)
                already_stopped.append(model_name)
            except SessionBackendError as exc:
                logger.error("Backend error stopping '%s': %s", model_name, exc)
                failed.append({"model": model_name, "error": str(exc)})
            except HTTPException as exc:
                failed.append({"model": model_name, "error": exc.detail})
            except Exception as exc:  # noqa: BLE001
                logger.error("Unexpected error stopping '%s': %s", model_name, exc)
                failed.append({"model": model_name, "error": str(exc)})

        if not orchestrator.controllers:
            orchestrator.active_project_directory = None
            orchestrator.project_state = "IDLE"
            orchestrator.should_stop_discussion = True
            orchestrator.discussion_state = "IDLE"

        return {
            "success": not failed,
            "stopped": stopped,
            "already_stopped": already_stopped,
            "failed": failed,
        }


def register_discussion_routes(app: FastAPI) -> None:
    """Attach discussion orchestration endpoints to the provided FastAPI app."""

    def _normalize_participants(
        orchestrator: "DevelopmentTeamOrchestrator",
        requested: Optional[Sequence[str]],
    ) -> List[str]:
        if requested:
            return normalize_model_names(requested)
        available = list(orchestrator.controllers.keys())
        if not available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active controllers available for discussion",
            )
        return available

    def _order_participants(participants: List[str], starting_model: str) -> List[str]:
        if starting_model not in participants:
            return participants
        idx = participants.index(starting_model)
        return participants[idx:] + participants[:idx]

    @app.post("/api/discussion/configure", tags=["discussion"])
    async def configure_discussion(
        config: DiscussionConfig,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        participants = _normalize_participants(orchestrator, config.participants)
        if len(participants) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least two participants are required for a discussion",
            )

        starting_model = (
            config.starting_model.strip().lower()
            if isinstance(config.starting_model, str) and config.starting_model.strip()
            else participants[0]
        )
        if starting_model not in participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"starting_model '{config.starting_model}' is not part of the participant list",
            )

        ordered_participants = _order_participants(participants, starting_model)
        try:
            max_turns = max(1, int(config.max_turns))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="max_turns must be an integer >= 1",
            ) from None

        normalized_config = {
            "max_turns": max_turns,
            "starting_model": starting_model,
            "participants": ordered_participants,
            "discussion_topic": (config.discussion_topic or "").strip() or None,
            "include_history": bool(config.include_history),
            "log_level": (config.log_level or "").upper() or None,
        }

        orchestrator.discussion_config = normalized_config
        return {"status": "configured", "config": normalized_config}

    @app.post("/api/discussion/start", tags=["discussion"])
    async def start_discussion(orchestrator=Depends(get_orchestrator)) -> Dict[str, Any]:
        if orchestrator.project_state != "OPEN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Open a project before starting a discussion",
            )

        if len(orchestrator.controllers) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least two active controllers are required",
            )

        if orchestrator.discussion_state == "RUNNING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discussion already running",
            )

        if orchestrator.discussion_thread and orchestrator.discussion_thread.is_alive():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Discussion thread already active",
            )

        config = orchestrator.discussion_config
        if not config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configure the discussion before starting",
            )

        participants = list(config.get("participants") or [])
        if len(participants) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discussion configuration must include at least two participants",
            )

        missing = [name for name in participants if name not in orchestrator.controllers]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Participants not running: {', '.join(missing)}",
            )

        topic = config.get("discussion_topic") or "General discussion"
        max_turns = int(config.get("max_turns") or 10)
        include_history = bool(config.get("include_history", True))
        log_level_override = config.get("log_level")
        orchestrator.apply_discussion_log_level(log_level_override)

        orchestrator.should_stop_discussion = False
        orchestrator.discussion_state = "RUNNING"
        orchestrator.discussion_error = None

        def _discussion_worker() -> None:
            result = None
            try:
                result = orchestrator.start_discussion(
                    topic,
                    participants=participants,
                    max_turns=max_turns,
                    include_history=include_history,
                )
            except Exception as exc:  # noqa: BLE001
                orchestrator.discussion_error = str(exc)
                logger.exception("Discussion failed: %s", exc)
            finally:
                # Cache the final turn count before manager is cleared
                if result and "conversation" in result:
                    orchestrator.last_discussion_turns = len(result["conversation"])
                    logger.info("Discussion completed with %d turns", orchestrator.last_discussion_turns)
                elif orchestrator.discussion_manager:
                    snapshot = getattr(orchestrator.discussion_manager, "get_status_snapshot", lambda: {})()
                    orchestrator.last_discussion_turns = snapshot.get("turn_counter", 0)
                    logger.info("Discussion completed, cached turn count: %d", orchestrator.last_discussion_turns)
                orchestrator.should_stop_discussion = False
                orchestrator.discussion_state = "IDLE"
                orchestrator.discussion_thread = None
                orchestrator.reset_discussion_log_level()

        thread = threading.Thread(target=_discussion_worker, name="orchestrated-discussion", daemon=True)
        orchestrator.discussion_thread = thread
        thread.start()

        return {
            "status": "started",
            "topic": topic,
            "max_turns": max_turns,
            "participants": participants,
        }

    @app.post("/api/discussion/extend", tags=["discussion"])
    async def extend_discussion(
        request: ExtendDiscussionRequest,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        manager = getattr(orchestrator, "discussion_manager", None)
        state = getattr(orchestrator, "discussion_state", "IDLE")
        if manager is None or state not in {"RUNNING", "PAUSED"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active discussion to extend",
            )

        extend_by = int(request.extend_by)
        if extend_by <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="extend_by must be >= 1",
            )

        config = orchestrator.discussion_config or {}
        try:
            new_total = manager.extend_turn_limit(extend_by)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to extend discussion turns: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extend discussion turns: {exc}",
            ) from exc

        config["max_turns"] = new_total
        orchestrator.discussion_config = config

        return {
            "status": "extended",
            "extend_by": extend_by,
            "max_turns": new_total,
            "discussion_state": orchestrator.discussion_state,
        }

    @app.post("/api/discussion/stop", tags=["discussion"])
    async def stop_discussion(orchestrator=Depends(get_orchestrator)) -> Dict[str, Any]:
        thread = orchestrator.discussion_thread
        if thread is None or not thread.is_alive():
            orchestrator.should_stop_discussion = False
            orchestrator.discussion_state = "IDLE"
            return {"status": "stopped", "already_stopped": True}

        orchestrator.should_stop_discussion = True
        logger.info("Stop discussion requested, waiting for current turn to complete...")
        thread.join(timeout=30.0)
        if thread.is_alive():
            logger.error("Discussion thread did not stop within 30 seconds")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Discussion did not stop within 30 seconds. The current model may be taking a long time to respond. Try again or use the KILL button if needed.",
            )

        orchestrator.discussion_thread = None
        orchestrator.discussion_state = "IDLE"
        orchestrator.should_stop_discussion = False
        logger.info("Discussion stopped successfully")
        return {"status": "stopped", "already_stopped": False}

    @app.post("/api/discussion/human/submit", tags=["discussion", "human"])
    async def submit_human_turn(
        request: HumanSubmitRequest,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        """
        Submit a human participant's turn response.

        Phase 3: HitL - Records the human's response as a turn in the conversation history,
        clears the waiting_on_human flag, and allows the discussion to continue.
        """
        import time
        conv_mgr = orchestrator.discussion_manager
        if conv_mgr is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active discussion",
            )

        if not conv_mgr._waiting_on_human:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not currently waiting for human input",
            )

        # Validate empty submission if configured
        human_cfg = get_config().get_section("human") or {}
        allow_empty = human_cfg.get("allow_empty_submissions", False)
        if not allow_empty and not request.response.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty responses are not allowed",
            )

        speaker = conv_mgr._pending_turn_participant
        if not speaker:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Human turn state is inconsistent (no pending participant)",
            )

        # Create turn record for human response
        turn_record = {
            "turn": conv_mgr._turn_counter,
            "speaker": speaker,
            "topic": conv_mgr.discussion_config.get("discussion_topic") if conv_mgr.discussion_config else "",
            "prompt": "",  # Humans don't get prompts
            "response": request.response.strip(),
            "metadata": {
                "human_turn": True,
                "submitted_at": time.time(),
            },
        }

        # Get response marker from config
        response_marker = human_cfg.get("response_marker", "👤")
        turn_record["response_marker"] = response_marker

        # Add to conversation history
        conv_mgr.history.append(turn_record)
        conv_mgr._turn_counter += 1

        # Store turn and record activity
        conv_mgr._store_turn(turn_record)
        conv_mgr._record_turn_activity(speaker, turn_record)

        # Clear waiting state
        conv_mgr._waiting_on_human = False
        conv_mgr._pending_turn_participant = None
        conv_mgr._human_turn_started_at = None

        logger.info("Human turn submitted for '%s' (turn %d)", speaker, turn_record["turn"])

        # Phase 4: HitL - Emit human_turn_completed event
        await discussion_event_manager.broadcast({
            "type": "human_turn_completed",
            "speaker": speaker,
            "turn": turn_record["turn"],
            "response_length": len(request.response.strip()),
            "timestamp": time.time(),
        })

        return {
            "status": "submitted",
            "turn": turn_record["turn"],
            "speaker": speaker,
            "response_length": len(request.response.strip()),
        }

    @app.post("/api/discussion/human/skip", tags=["discussion", "human"])
    async def skip_human_turn(orchestrator=Depends(get_orchestrator)) -> Dict[str, Any]:
        """
        Skip the current human turn without submitting a response.

        Phase 3: HitL - Records a skipped turn in history and advances to the next speaker.
        """
        conv_mgr = orchestrator.discussion_manager
        if conv_mgr is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active discussion",
            )

        if not conv_mgr._waiting_on_human:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not currently waiting for human input",
            )

        speaker = conv_mgr._pending_turn_participant
        if not speaker:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Human turn state is inconsistent (no pending participant)",
            )

        # Record the turn before getting turn number (counter increments inside)
        turn_before = conv_mgr._turn_counter
        conv_mgr._record_human_skip(speaker, timeout=False)

        # Phase 4: HitL - Emit human_turn_skipped event
        await discussion_event_manager.broadcast({
            "type": "human_turn_skipped",
            "speaker": speaker,
            "turn": turn_before,
            "timestamp": time.time(),
        })

        return {
            "status": "skipped",
            "turn": turn_before,
            "speaker": speaker,
        }

    @app.post("/api/discussion/human/bypass/toggle", tags=["discussion", "human"])
    async def toggle_bypass_human(orchestrator=Depends(get_orchestrator)) -> Dict[str, Any]:
        """
        Toggle the bypass_human flag to skip human turns in the rotation.

        Phase 3: HitL - When enabled, human turns are skipped in favor of the next AI participant.
        """
        conv_mgr = orchestrator.discussion_manager
        if conv_mgr is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active discussion",
            )

        # Toggle the flag
        conv_mgr._bypass_human = not conv_mgr._bypass_human
        new_state = conv_mgr._bypass_human

        logger.info("Bypass human flag toggled to: %s", new_state)

        # Phase 4: HitL - Emit bypass_human_toggled event
        await discussion_event_manager.broadcast({
            "type": "bypass_human_toggled",
            "bypass_human": new_state,
            "timestamp": time.time(),
        })

        return {
            "status": "toggled",
            "bypass_human": new_state,
        }

    @app.get("/api/discussion/status", tags=["discussion"])
    async def discussion_status(orchestrator=Depends(get_orchestrator)) -> Dict[str, Any]:
        snapshot = orchestrator.get_discussion_status_snapshot()
        thread = orchestrator.discussion_thread
        snapshot["thread_alive"] = bool(thread and thread.is_alive())
        snapshot["config"] = orchestrator.discussion_config
        return snapshot


def register_instruction_routes(app: FastAPI) -> None:
    """Attach instruction file management endpoints to the provided FastAPI app."""

    @app.get("/api/instructions/{model_name}", tags=["instructions"])
    async def get_instruction_file(
        model_name: str,
        project_directory: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Fetch the instruction file for a given model.

        Args:
            model_name: Model identifier (e.g., "Claude", "Gemini")
            project_directory: Optional base directory (defaults to repository root)

        Returns:
            Dictionary with "content" key containing the file contents
        """
        if model_name not in INSTRUCTION_FILES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown model '{model_name}'",
            )

        # Determine base path
        if project_directory:
            base_path = Path(project_directory)
        else:
            # Default to repository root (2 levels up from src/orchestrator/)
            base_path = Path(__file__).resolve().parents[2]

        file_path = base_path / INSTRUCTION_FILES[model_name]

        try:
            content = file_path.read_text(encoding="utf-8")
            logger.debug("Read instruction file: %s", file_path)
            return {"content": content}
        except FileNotFoundError:
            logger.warning("Instruction file not found: %s", file_path)
            return {"content": ""}

    @app.post("/api/instructions/{model_name}", tags=["instructions"])
    async def save_instruction_file(
        model_name: str,
        instruction_file: InstructionFile,
    ) -> Dict[str, str]:
        """
        Save the instruction file for a given model.

        Args:
            model_name: Model identifier
            instruction_file: Request body with content and optional project_directory

        Returns:
            Success message
        """
        if model_name not in INSTRUCTION_FILES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown model '{model_name}'",
            )

        # Determine base path
        if instruction_file.project_directory:
            base_path = Path(instruction_file.project_directory)
        else:
            base_path = Path(__file__).resolve().parents[2]

        file_path = base_path / INSTRUCTION_FILES[model_name]

        try:
            file_path.write_text(instruction_file.content, encoding="utf-8")
            logger.info("Saved instruction file: %s", file_path)
            return {"message": "File saved successfully"}
        except Exception as exc:
            logger.error("Failed to save instruction file %s: %s", file_path, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            )


def register_settings_routes(app: FastAPI) -> None:
    """Attach model settings overrides endpoints to the FastAPI app."""

    @app.get("/api/settings/model/{model_name}", tags=["settings"])
    async def get_model_settings(
        model_name: str,
        project_directory: str = Query(..., description="Absolute project directory path"),
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        model_key = normalize_single_model_name(model_name)
        project_dir = resolve_project_directory(project_directory)
        config_loader = get_config()
        config_section = dict(config_loader.get_section(model_key) or {})
        overrides = orchestrator.get_model_config_overrides(project_dir, model_key)

        fields_payload: List[Dict[str, Any]] = []
        for field_meta in iter_model_setting_fields(model_key):
            default_value = get_field_default_value(field_meta, config_section)
            effective_value = overrides.get(field_meta["key"], default_value)
            fields_payload.append(
                {
                    "key": field_meta["key"],
                    "label": field_meta["label"],
                    "description": field_meta.get("description"),
                    "type": field_meta.get("type", "number"),
                    "value_type": field_meta.get("value_type", "float"),
                    "min": field_meta.get("min"),
                    "max": field_meta.get("max"),
                    "step": field_meta.get("step"),
                    "default": default_value,
                    "value": effective_value,
                    "overridden": field_meta["key"] in overrides,
                }
            )

        return {
            "model": model_key,
            "project_directory": str(project_dir),
            "fields": fields_payload,
            "notes": "Overrides apply the next time the model session starts.",
        }

    @app.post("/api/settings/model/{model_name}", tags=["settings"])
    async def update_model_settings(
        model_name: str,
        payload: ModelSettingsUpdate,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        model_key = normalize_single_model_name(model_name)
        project_dir = resolve_project_directory(payload.project_directory)
        overrides_payload = payload.overrides or {}

        allowed_fields = {
            field["key"]: field
            for field in iter_model_setting_fields(model_key)
        }
        normalized_overrides: Dict[str, Any] = {}
        for key, raw_value in overrides_payload.items():
            field_meta = allowed_fields.get(key)
            if field_meta is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field '{key}' is not configurable for model '{model_key}'",
                )
            normalized_overrides[key] = convert_setting_value(
                field_meta,
                raw_value,
                allow_none=False,
            )

        orchestrator.set_model_config_overrides(project_dir, model_key, normalized_overrides)
        return {
            "status": "updated",
            "model": model_key,
            "project_directory": str(project_dir),
            "overrides": normalized_overrides,
        }

    @app.delete("/api/settings/model/{model_name}", tags=["settings"])
    async def reset_model_settings(
        model_name: str,
        project_directory: str = Query(..., description="Absolute project directory path"),
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, Any]:
        model_key = normalize_single_model_name(model_name)
        project_dir = resolve_project_directory(project_directory)
        cleared = orchestrator.clear_model_config_overrides(project_dir, model_key)
        return {
            "status": "cleared" if cleared else "noop",
            "model": model_key,
            "project_directory": str(project_dir),
        }


def register_filesystem_routes(app: FastAPI) -> None:
    """Attach filesystem browsing endpoints to the provided FastAPI app."""

    @app.post("/api/fs/browse", tags=["filesystem"])
    async def browse_filesystem(directory_path: DirectoryPath) -> Dict[str, Any]:
        """
        Browse filesystem directory contents.

        Args:
            directory_path: Request body with path to browse

        Returns:
            Dictionary with "path" and "contents" (list of files/folders)
        """
        logger.debug("Browsing path: %s", directory_path.path)
        try:
            base_path = Path(directory_path.path).resolve()
            if not base_path.is_dir():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid directory path",
                )

            contents = []
            for item in sorted(base_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                contents.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "path": str(item),
                })

            return {"path": str(base_path), "contents": contents}
        except PermissionError as exc:
            logger.warning("Permission denied browsing %s: %s", directory_path.path, exc)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        except Exception as exc:
            logger.error("Error browsing path %s: %s", directory_path.path, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            )


STREAM_POLL_INTERVAL_SECONDS = 0.5


def normalize_scrollback_text(text: str) -> str:
    """
    Remove trailing blank lines from a tmux scrollback capture.

    Tmux captures often pad the buffer with empty rows equal to the pane height,
    which results in WebSocket clients displaying a blank viewport initially.
    This helper trims those trailing blank lines while preserving intentional
    whitespace elsewhere. A trailing newline is preserved so line breaks render
    naturally in the UI.
    """
    if not text:
        return ""

    lines = text.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


def compute_scrollback_event(previous: str, current: str) -> Optional[Dict[str, str]]:
    """
    Determine the appropriate payload describing the transition from previous to current.

    Returns:
        Dict containing "type" (snapshot|append|reset) and "content". None if unchanged.
    """
    if not previous:
        if current:
            return {"type": "snapshot", "content": current}
        return None

    if current.startswith(previous):
        delta = current[len(previous):]
        if delta:
            return {"type": "append", "content": delta}
        return None

    return {"type": "reset", "content": current}


async def stream_controller_output(
    websocket: WebSocket,
    orchestrator: Optional["DevelopmentTeamOrchestrator"],
    model_name: str,
) -> None:
    """Stream tmux scrollback snapshots over the given WebSocket connection."""

    await websocket.accept()
    logger.debug("WebSocket accepted for model '%s'", model_name)

    if orchestrator is None:
        await websocket.send_json({
            "type": "error",
            "model": model_name,
            "message": "Orchestrator is not available",
        })
        await websocket.close(code=1011)
        return

    if model_name not in orchestrator.controllers:
        await websocket.send_json({
            "type": "error",
            "model": model_name,
            "message": f"Unknown model '{model_name}'",
        })
        await websocket.close(code=1008)
        return

    controller = orchestrator.controllers[model_name]
    capture: Optional[Callable[[], str]] = getattr(controller, "capture_scrollback", None)
    if not callable(capture):
        logger.warning("Model '%s' lacks capture_scrollback()", model_name)
        await websocket.send_json({
            "type": "error",
            "model": model_name,
            "message": "capture_scrollback unavailable on controller",
        })
        await websocket.close(code=1011)
        return

    capture_callable = cast(Callable[[], str], capture)
    previous = ""
    last_status_payload: Optional[Dict[str, Any]] = None
    last_status_sent_at = 0.0

    try:
        initial_snapshot = await asyncio.to_thread(capture_callable)
        initial_snapshot = normalize_scrollback_text(initial_snapshot)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Initial capture failed for %s: %s", model_name, exc)
        await websocket.send_json({
            "type": "error",
            "model": model_name,
            "message": f"capture_scrollback failed: {exc}",
        })
        await websocket.close(code=1011)
        return

    try:
        event = compute_scrollback_event(previous, initial_snapshot)
        if event:
            payload = {
                "model": model_name,
                "timestamp": datetime.utcnow().isoformat(),
                **event,
            }
            logger.debug("Initial snapshot payload for '%s': type=%s size=%d", model_name, event["type"], len(event["content"]))
            await websocket.send_json(payload)
            previous = initial_snapshot
        else:
            previous = initial_snapshot
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for model '%s' during initial snapshot", model_name)
        return

    try:
        while True:
            try:
                snapshot = await asyncio.to_thread(capture_callable)
                snapshot = normalize_scrollback_text(snapshot)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to capture scrollback for %s: %s", model_name, exc)
                await websocket.send_json({
                    "type": "error",
                    "model": model_name,
                    "message": f"capture_scrollback failed: {exc}",
                })
                await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)
                continue

            event = compute_scrollback_event(previous, snapshot)
            if event:
                payload = {
                    "model": model_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    **event,
                }
                logger.debug("Streaming update for '%s': type=%s size=%d", model_name, event["type"], len(event["content"]))
                await websocket.send_json(payload)
                previous = snapshot
            else:
                logger.debug("No diff for '%s' (previous=%d chars, current=%d chars)", model_name, len(previous), len(snapshot))

            if orchestrator is not None:
                now = time.time()
                if now - last_status_sent_at >= 2.0:
                    status_snapshot = orchestrator.get_discussion_status_snapshot()
                    manager_snapshot = status_snapshot.get("manager") or {}
                    status_payload = {
                        "type": "discussion_status",
                        "project_state": status_snapshot.get("project_state"),
                        "state": status_snapshot.get("discussion_state"),
                        "turn": manager_snapshot.get("turn_counter"),
                        "speaker": manager_snapshot.get("current_agent"),
                        "pending_injections": manager_snapshot.get("pending_injections"),
                        "error": status_snapshot.get("error"),
                    }
                    config = status_snapshot.get("config")
                    if config:
                        status_payload["config"] = config
                    if status_payload != last_status_payload:
                        await websocket.send_json(status_payload)
                        last_status_payload = status_payload
                    last_status_sent_at = now

            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for model '%s'", model_name)
    except asyncio.CancelledError:
        # Graceful cancellation during shutdown
        logger.debug("WebSocket task cancelled for model '%s' during shutdown", model_name)
        try:
            await websocket.close(code=1001, reason="Server shutting down")
        except Exception:  # noqa: BLE001
            pass  # Connection may already be closed
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error streaming %s: %s", model_name, exc)
        try:
            await websocket.close(code=1011)
        except Exception:  # noqa: BLE001
            pass  # Connection may already be closed


def register_stream_routes(app: FastAPI) -> None:
    """Attach WebSocket streaming routes for session output."""

    @app.websocket("/ws/session/{model_name}")
    async def stream_session_output(websocket: WebSocket, model_name: str) -> None:
        orchestrator = getattr(websocket.app.state, "orchestrator", None)
        await stream_controller_output(websocket, orchestrator, model_name)

    @app.websocket("/ws/discussion/events")
    async def discussion_events_stream(websocket: WebSocket) -> None:
        """
        Phase 4: HitL - WebSocket endpoint for real-time discussion events.

        Clients connect to receive events about human turns, bypass toggles,
        and other discussion state changes.
        """
        await discussion_event_manager.connect(websocket)
        try:
            # Keep connection alive and wait for disconnect
            while True:
                # Receive messages from client (ping/pong or other client events)
                await websocket.receive_text()
        except WebSocketDisconnect:
            discussion_event_manager.disconnect(websocket)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Discussion events WebSocket error: %s", exc)
            discussion_event_manager.disconnect(websocket)

    @app.post("/api/fs/prepare-project", tags=["filesystem"])
    async def prepare_project(directory_path: DirectoryPath) -> Dict[str, Any]:
        """
        Prepare a project directory by creating instruction files if they don't exist.

        This should be called when the user selects a project directory in the UI,
        BEFORE clicking "Open Project", so the files exist for customization.

        Args:
            directory_path: Request body with path field

        Returns:
            Status of file preparation
        """
        try:
            project_dir = resolve_project_directory(directory_path.path)
            created_files = []
            existing_files = []

            # Create instruction files for all known models
            for model_name in INSTRUCTION_FILES.keys():
                model_lower = model_name.lower()
                instruction_file = INSTRUCTION_FILES.get(model_name)
                file_path = project_dir / instruction_file

                if file_path.exists():
                    existing_files.append(instruction_file)
                else:
                    # Create new file with template
                    ensure_instruction_file_security(project_dir, model_lower)
                    created_files.append(instruction_file)

            return {
                "project_directory": str(project_dir),
                "created_files": created_files,
                "existing_files": existing_files,
                "message": f"Created {len(created_files)} instruction files" if created_files else "All instruction files already exist"
            }

        except Exception as exc:
            logger.error("Failed to prepare project: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to prepare project: {str(exc)}"
            )

    @app.post("/api/fs/create-folder", tags=["filesystem"])
    async def create_folder(new_folder: NewFolder) -> Dict[str, str]:
        """
        Create a new folder in the specified directory.

        Args:
            new_folder: Request body with path and folderName

        Returns:
            Success message
        """
        logger.debug("Creating folder: %s in %s", new_folder.folderName, new_folder.path)
        try:
            path = Path(new_folder.path).resolve()
            folder_name = new_folder.folderName
            new_folder_path = path / folder_name
            new_folder_path.mkdir(parents=False, exist_ok=False)
            logger.info("Created folder: %s", new_folder_path)
            return {"message": f"Folder '{folder_name}' created successfully"}
        except FileExistsError:
            logger.warning("Folder already exists: %s", new_folder_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Folder with that name already exists",
            )
        except PermissionError as exc:
            logger.warning("Permission denied creating folder %s: %s", new_folder_path, exc)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        except Exception as exc:
            logger.error("Error creating folder %s: %s", new_folder_path, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            )
