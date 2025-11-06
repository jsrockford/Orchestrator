"""FastAPI application exposing orchestrator control and monitoring endpoints."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from .orchestrator import DevelopmentTeamOrchestrator

DEFAULT_CONTROL_FIFO = Path("/tmp/orchestrator_control")
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


async def write_fifo_message(
    message: str,
    *,
    fifo_path: Path = DEFAULT_CONTROL_FIFO,
    retries: int = 3,
    delay_seconds: float = 0.1,
) -> None:
    """
    Write a control message to the orchestrator FIFO with retry logic.

    Args:
        message: Command to write, should include newline terminator.
        fifo_path: Filesystem path to the named pipe.
        retries: Number of attempts before raising an error.
        delay_seconds: Wait duration between retries.
    """
    attempt = 0
    while True:
        try:
            payload = message if message.endswith("\n") else f"{message}\n"
            with fifo_path.open("w", encoding="utf-8") as fifo:
                fifo.write(payload)
                fifo.flush()
            logger.debug("Wrote command to control FIFO=%s message=%r", fifo_path, payload)
            return
        except FileNotFoundError as exc:
            logger.warning(
                "Control FIFO missing at %s (attempt %d/%d): %s",
                fifo_path,
                attempt + 1,
                retries,
                exc,
            )
            attempt += 1
        except OSError as exc:  # EPIPE, ENXIO, etc.
            logger.warning(
                "Failed to write control command to %s (attempt %d/%d): %s",
                fifo_path,
                attempt + 1,
                retries,
                exc,
            )
            attempt += 1

        if attempt >= retries:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to write to control FIFO after {retries} attempts",
            )
        await asyncio.sleep(delay_seconds)


def format_key_command(model_name: str, key_name: str) -> str:
    """Return a KEY command string for the control channel."""
    normalized = key_name.strip()
    return f"KEY {model_name} {normalized}"


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
    async def pause(_: "DevelopmentTeamOrchestrator" = Depends(get_orchestrator)) -> Dict[str, str]:
        await write_fifo_message("PAUSE")
        return {"status": "paused"}

    @app.post("/api/control/resume", tags=["control"])
    async def resume(_: "DevelopmentTeamOrchestrator" = Depends(get_orchestrator)) -> Dict[str, str]:
        await write_fifo_message("RESUME")
        return {"status": "resumed"}

    @app.post("/api/control/{model_name}/key/{key_name}", tags=["control"])
    async def send_key(
        model_name: str,
        key_name: str,
        orchestrator=Depends(get_orchestrator),
    ) -> Dict[str, str]:
        validate_model_name(orchestrator, model_name)
        normalized = normalize_key_name(key_name)
        command = format_key_command(model_name, normalized)
        await write_fifo_message(command)
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
