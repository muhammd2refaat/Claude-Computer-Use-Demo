"""File management routes for session outputs."""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions/{session_id}/files", tags=["files"])

BASE_OUTPUT_DIR = Path("/tmp/outputs")


def get_session_output_dir(session_id: str) -> Path:
    """Get the output directory for a specific session.

    Files are isolated per session to prevent cross-session data leakage.
    Falls back to checking the shared directory for backwards compatibility.
    """
    return BASE_OUTPUT_DIR / session_id


class FileInfo(BaseModel):
    name: str
    size: int
    created_at: float
    path: str


class FileListResponse(BaseModel):
    files: List[FileInfo]
    total: int


@router.get("", response_model=FileListResponse)
async def list_files(session_id: str):
    """List all files created during a session.

    Files are stored in /tmp/outputs/{session_id}/ and typically include screenshots.
    Also checks the shared /tmp/outputs/ directory for backwards compatibility.
    """
    files = []

    # Check session-specific directory first
    session_dir = get_session_output_dir(session_id)
    dirs_to_check = [session_dir]

    # Also check shared directory for backwards compatibility
    if BASE_OUTPUT_DIR.exists():
        dirs_to_check.append(BASE_OUTPUT_DIR)

    try:
        seen_names = set()
        for output_dir in dirs_to_check:
            if not output_dir.exists():
                continue
            for file_path in output_dir.glob("*"):
                if file_path.is_file() and file_path.name not in seen_names:
                    # Skip session subdirectories
                    if file_path.parent == BASE_OUTPUT_DIR and (BASE_OUTPUT_DIR / file_path.name).is_dir():
                        continue
                    stat = file_path.stat()
                    files.append(FileInfo(
                        name=file_path.name,
                        size=stat.st_size,
                        created_at=stat.st_mtime,
                        path=str(file_path),
                    ))
                    seen_names.add(file_path.name)

        # Sort by creation time, newest first
        files.sort(key=lambda f: f.created_at, reverse=True)

        return FileListResponse(files=files, total=len(files))
    except Exception as e:
        logger.error(f"Failed to list files for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


@router.get("/{filename}")
async def download_file(session_id: str, filename: str):
    """Download a specific file from the session outputs."""
    # Sanitize filename to prevent directory traversal
    safe_filename = Path(filename).name

    # Check session-specific directory first
    session_dir = get_session_output_dir(session_id)
    file_path = session_dir / safe_filename

    # Fallback to shared directory for backwards compatibility
    if not file_path.exists():
        file_path = BASE_OUTPUT_DIR / safe_filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        media_type="application/octet-stream",
    )
