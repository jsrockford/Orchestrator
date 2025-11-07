"""FastAPI application exposing orchestrator control and monitoring endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Sequence, Type, cast

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..controllers import ClaudeController, CodexController, GeminiController, QwenController
from ..controllers.session_backend import SessionBackendError, SessionNotFoundError
from ..utils.exceptions import SessionAlreadyExists
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .orchestrator import DevelopmentTeamOrchestrator

logger = get_logger("orchestrator.web_api")


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


def create_app(orchestrator: "DevelopmentTeamOrchestrator") -> FastAPI:
    """
    Build a FastAPI application bound to the provided orchestrator instance.

    Args:
        orchestrator: Live orchestrator instance used to satisfy API requests.
    """

    app = FastAPI(title="Development Team Orchestrator API", version="0.1.0")
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
    register_instruction_routes(app)
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
    """Normalize and validate requested model identifiers."""
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

        if candidate not in CONTROLLER_FACTORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown model '{raw}'. Supported models: {', '.join(sorted(CONTROLLER_FACTORIES))}",
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

        return {"status": "paused", "controllers": list(controllers.keys())}

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
        return {"status": "resumed", "controllers": list(controllers.keys())}

    @app.post("/api/control/{model_name}/key/{key_name}", tags=["control"])
    async def send_key(
        model_name: str,
        key_name: str,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, str]:
        validate_model_name(orchestrator, model_name)
        normalized = normalize_key_name(key_name)
        controller = orchestrator.controllers[model_name]
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
                controller = factory(working_dir=str(project_dir))
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

        return {
            "success": not failed,
            "stopped": stopped,
            "already_stopped": already_stopped,
            "failed": failed,
        }


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

            await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for model '%s'", model_name)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error streaming %s: %s", model_name, exc)
        await websocket.close(code=1011)


def register_stream_routes(app: FastAPI) -> None:
    """Attach WebSocket streaming routes for session output."""

    @app.websocket("/ws/session/{model_name}")
    async def stream_session_output(websocket: WebSocket, model_name: str) -> None:
        orchestrator = getattr(websocket.app.state, "orchestrator", None)
        await stream_controller_output(websocket, orchestrator, model_name)

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
