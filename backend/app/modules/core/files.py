"""Image uploads (patient photos, facility logo): checked by declared type, size and the file's own signature,
because these files are served back to browsers."""
import os

from fastapi import HTTPException, UploadFile

from ...config import settings

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MEDIA_TYPES = {ext: mt for mt, ext in IMAGE_TYPES.items()}


def _looks_like(data: bytes, ext: str) -> bool:
    return {".jpg": data[:3] == b"\xff\xd8\xff", ".png": data[:4] == b"\x89PNG",
            ".webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP"}[ext]


async def save_image(file: UploadFile, folder: str, name: str, old_path: str | None, what: str = "Photo") -> str:
    """Validates and writes the upload to <data_dir>/<folder>/<name><ext>; returns the path."""
    ext = IMAGE_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(415, f"{what} must be a JPEG, PNG or WebP image")
    limit = settings.max_photo_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"{what} is larger than {settings.max_photo_mb} MB")
    if not data:
        raise HTTPException(422, f"{what} file is empty")
    if not _looks_like(data, ext):
        raise HTTPException(415, f"{what} file is not a valid image")
    target = os.path.join(settings.data_dir, folder)
    os.makedirs(target, exist_ok=True)
    path = os.path.join(target, f"{name}{ext}")
    if old_path and old_path != path and os.path.exists(old_path):
        os.remove(old_path)
    with open(path, "wb") as f:
        f.write(data)
    return path


def media_type(path: str) -> str:
    return MEDIA_TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
