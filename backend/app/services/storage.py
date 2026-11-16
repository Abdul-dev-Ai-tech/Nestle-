"""Secure file storage for evidence frames and employee photos.

* Files are validated as real images and re-encoded (strips metadata and any embedded payload).
* Names are random; user-supplied names are never used on disk.
* Files are served only through authenticated, permission-checked API endpoints.
"""
import io
import secrets
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings
from app.core.time import utcnow

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PIXELS = 4096 * 4096


def _root() -> Path:
    root = Path(get_settings().STORAGE_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_image(data: bytes) -> Image.Image:
    max_bytes = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if len(data) > max_bytes:
        raise HTTPException(413,
                            f"Image is larger than {get_settings().MAX_UPLOAD_MB} MB")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is not a valid image") from None
    if img.format not in ALLOWED_FORMATS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPEG, PNG or WebP images are accepted")
    if img.width * img.height > MAX_PIXELS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image dimensions are too large")
    return img


async def read_upload(file: UploadFile) -> bytes:
    limit = get_settings().MAX_UPLOAD_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413,
                            f"File is larger than {get_settings().MAX_UPLOAD_MB} MB")
    return data


def save_image(data: bytes, category: str, *, max_side: int = 1600) -> str:
    """Validate, re-encode as JPEG and store. Returns a path relative to the storage root."""
    img = validate_image(data).convert("RGB")
    img.thumbnail((max_side, max_side))
    folder = _root() / category / utcnow().strftime("%Y/%m")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{secrets.token_hex(16)}.jpg"
    img.save(path, "JPEG", quality=85, optimize=True)
    return str(path.relative_to(_root())).replace("\\", "/")


def resolve(rel_path: str | None) -> Path | None:
    """Resolve a stored relative path, refusing anything outside the storage root."""
    if not rel_path:
        return None
    root = _root()
    path = (root / rel_path).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def delete(rel_path: str | None) -> None:
    path = resolve(rel_path)
    if path:
        path.unlink(missing_ok=True)


def purge_evidence_older_than(days: int) -> int:
    """Delete evidence files older than the retention period. Returns the number removed."""
    cutoff = (utcnow() - timedelta(days=days)).timestamp()
    removed = 0
    folder = _root() / "evidence"
    if folder.is_dir():
        for f in folder.rglob("*.jpg"):
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                removed += 1
    return removed
