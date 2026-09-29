#!/usr/bin/env python3
"""Single entrypoint: builds the frontend if stale, then starts the backend.

Usage: python scripts/launch.py [--no-build] [--host HOST] [--port PORT]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
BACKEND_DIR = REPO_ROOT / "backend"


def frontend_is_stale() -> bool:
    if not FRONTEND_DIST.is_dir():
        return True
    dist_mtime = max((p.stat().st_mtime for p in FRONTEND_DIST.rglob("*") if p.is_file()), default=0)
    src_dir = FRONTEND_DIR / "src"
    if not src_dir.is_dir():
        return False
    src_mtime = max((p.stat().st_mtime for p in src_dir.rglob("*") if p.is_file()), default=0)
    return src_mtime > dist_mtime


def build_frontend() -> None:
    if not (FRONTEND_DIR / "package.json").exists():
        print("No frontend/package.json yet; skipping frontend build.")
        return
    if shutil.which("npm") is None:
        print("npm not found on PATH; skipping frontend build. Serving backend API only.")
        return
    print("Building frontend...")
    subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=True)
    subprocess.run(["npm", "run", "build"], cwd=FRONTEND_DIR, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-build", action="store_true", help="Skip frontend build step")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload (dev)")
    args = parser.parse_args()

    if not args.no_build and frontend_is_stale():
        build_frontend()

    sys.path.insert(0, str(BACKEND_DIR))
    import uvicorn

    uvicorn.run(
        "simllm.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(BACKEND_DIR),
    )


if __name__ == "__main__":
    main()
