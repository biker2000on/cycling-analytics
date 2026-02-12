"""File storage service for FIT files.

Handles saving and deleting FIT files on the local filesystem.
Directory structure: {FIT_STORAGE_PATH}/{user_id}/{YYYY}/{MM}/{uuid}.fit
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


def save_fit_file(content: bytes, user_id: int) -> str:
    """Save FIT file content to disk in an organized directory structure.

    Args:
        content: Raw bytes of the FIT file.
        user_id: Owner user ID (used for directory partitioning).

    Returns:
        Relative file path from FIT_STORAGE_PATH root (e.g. "1/2026/02/abc123.fit").
    """
    settings = get_settings()
    now = datetime.now(UTC)

    # Build directory: {base}/{user_id}/{YYYY}/{MM}
    relative_dir = Path(str(user_id)) / str(now.year) / f"{now.month:02d}"
    full_dir = Path(settings.FIT_STORAGE_PATH) / relative_dir
    full_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    filename = f"{uuid.uuid4().hex}.fit"
    relative_path = str(relative_dir / filename)
    full_path = full_dir / filename

    full_path.write_bytes(content)

    logger.info(
        "fit_file_saved",
        user_id=user_id,
        path=relative_path,
        size_bytes=len(content),
    )

    return relative_path


def delete_fit_file(file_path: str) -> None:
    """Delete a FIT file from disk.

    Args:
        file_path: Relative path from FIT_STORAGE_PATH root.

    Silently ignores missing files (idempotent).
    """
    settings = get_settings()
    full_path = Path(settings.FIT_STORAGE_PATH) / file_path

    if full_path.exists():
        full_path.unlink()
        logger.info("fit_file_deleted", path=file_path)
    else:
        logger.warning("fit_file_not_found_for_deletion", path=file_path)
