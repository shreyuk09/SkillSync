"""Upload validation and safe file handling.

Uploaded resumes are sensitive documents, so this module is deliberately
strict:

* only an allow-list of extensions is accepted (never a deny-list);
* the size limit is enforced on the *bytes we actually read*, not on the
  client-supplied Content-Length header, which is trivially forged;
* the original filename is sanitised and only ever used as a display label --
  it is never joined onto a filesystem path, so `../../etc/passwd` is inert;
* the raw bytes stay in memory. Nothing is written to disk.
"""

import re
from pathlib import PurePosixPath
from typing import Tuple

from app.core.config import Settings
from app.core.errors import FileTooLarge, UnsupportedFileType

# A conservative allow-list of magic numbers. Used to catch a `.exe` that has
# been renamed to `.pdf` -- extension checks alone are not enough.
_MAGIC = {
    ".pdf": (b"%PDF-",),
    # DOCX is a ZIP container.
    ".docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    # WEBP and HEIC are RIFF/ISO-BMFF containers: the marker sits at byte 8,
    # after a length field, so the prefix test can't be used for them.
    ".tiff": (b"II*\x00", b"MM\x00*"),
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]")


def sanitize_filename(filename: str) -> str:
    """Strip any directory component and unsafe characters from a filename."""
    if not filename:
        return "document"
    # PurePosixPath().name drops everything before the last "/"; also handle "\".
    base = PurePosixPath(filename.replace("\\", "/")).name
    base = _SAFE_NAME.sub("_", base).strip(". ")
    return base[:120] or "document"


def get_extension(filename: str) -> str:
    name = sanitize_filename(filename)
    suffix = PurePosixPath(name).suffix.lower()
    return suffix


def validate_upload(filename: str, content: bytes, settings: Settings) -> Tuple[str, str]:
    """Validate an uploaded file.

    Returns `(safe_filename, extension)` or raises an `AppError` subclass.
    """
    safe_name = sanitize_filename(filename)
    extension = get_extension(safe_name)

    if extension not in settings.allowed_extensions:
        raise UnsupportedFileType(
            f"'{safe_name}' isn't a supported file type.",
            hint="Supported formats: " + ", ".join(settings.allowed_extensions),
        )

    if len(content) == 0:
        raise UnsupportedFileType(
            f"'{safe_name}' is empty.",
            hint="Pick a file that actually has content in it.",
        )

    if len(content) > settings.max_upload_bytes:
        actual_mb = len(content) / (1024 * 1024)
        raise FileTooLarge(
            f"'{safe_name}' is {actual_mb:.1f} MB, which is over the "
            f"{settings.max_upload_mb} MB limit.",
            hint="Compress the file or paste the text instead.",
        )

    expected_magic = _MAGIC.get(extension)
    if expected_magic and not any(content.startswith(prefix) for prefix in expected_magic):
        raise UnsupportedFileType(
            f"'{safe_name}' doesn't look like a real {extension.lstrip('.').upper()} file.",
            hint="The file contents don't match its extension. Try re-exporting it.",
        )

    return safe_name, extension


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB"):
        if num_bytes < 1024 or unit == "MB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} MB"
