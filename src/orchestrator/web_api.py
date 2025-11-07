"""FastAPI application exposing orchestrator control and monitoring endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Optional, cast

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


# Mapping of model names to their instruction files
INSTRUCTION_FILES = {
    "Claude": "CLAUDE.md",
    "Codex": "AGENTS.md",
    "Gemini": "GEMINI.md",
    "Qwen": "QWEN.md",
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
