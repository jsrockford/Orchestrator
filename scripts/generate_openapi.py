#!/usr/bin/env python3
"""
Generate the FastAPI OpenAPI schema for the Development Team Orchestrator.

Usage:
    python scripts/generate_openapi.py --output docs/openapi.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fastapi.openapi.utils import get_openapi

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.orchestrator.orchestrator import DevelopmentTeamOrchestrator  # noqa: E402
from src.orchestrator.web_api import create_app  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate OpenAPI schema for the orchestrator API.")
    parser.add_argument(
        "--output",
        default="docs/openapi.json",
        help="Path (relative to repo root) where the schema will be written.",
    )
    parser.add_argument(
        "--title",
        default="Development Team Orchestrator API",
        help="Override the OpenAPI document title.",
    )
    parser.add_argument(
        "--version",
        default="0.1.0",
        help="Override the OpenAPI document version.",
    )
    return parser.parse_args(argv)


def resolve_output_path(path_arg: str) -> Path:
    candidate = Path(path_arg)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:  # pragma: no cover - safety check
        raise SystemExit(f"Output path must live inside the repository (got: {candidate})") from exc
    candidate.parent.mkdir(parents=True, exist_ok=True)
    return candidate


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = resolve_output_path(args.output)

    orchestrator = DevelopmentTeamOrchestrator()
    app = create_app(orchestrator)

    schema = get_openapi(
        title=args.title or app.title or "Development Team Orchestrator API",
        version=args.version or app.version or "0.1.0",
        routes=app.routes,
    )

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(schema, handle, indent=2)
        handle.write("\n")

    print(f"Wrote OpenAPI schema to {output_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
