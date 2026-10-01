"""Text recognition for uploaded images.

Resumes and job descriptions often arrive as a screenshot or a phone photo.
Reading those needs OCR, and the usual answer -- Tesseract -- is a ~100 MB
system install that this project would otherwise never need.

macOS ships a good text recogniser in the Vision framework, so we call that
instead: no extra dependency, no network call, and the image never leaves the
machine. The helper is a few lines of Swift compiled on first use and cached
next to this file.

On any other platform, or if the toolchain is missing, `read_image()` raises
`OCRUnavailable` and the caller turns that into a clear message telling the
user to paste the text instead.
"""

import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

_SOURCE = Path(__file__).resolve().parent.parent / "vendor" / "ocr.swift"
_BINARY = _SOURCE.with_suffix("")
_TIMEOUT_SECONDS = 60


class OCRUnavailable(RuntimeError):
    """No usable text recogniser on this machine."""


def _compile() -> Optional[Path]:
    """Build the helper once. Returns None if it cannot be built."""
    if _BINARY.exists():
        return _BINARY
    if platform.system() != "Darwin" or not _SOURCE.exists():
        return None
    try:
        subprocess.run(
            ["swiftc", "-O", str(_SOURCE), "-o", str(_BINARY)],
            check=True, capture_output=True, timeout=240,
        )
        logger.info("Built the image OCR helper")
        return _BINARY
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
        logger.warning("Could not build the OCR helper: %s", exc)
        return None


def is_available() -> bool:
    return _compile() is not None


def read_image(content: bytes, suffix: str = ".png") -> str:
    """Return the text found in an image, or raise OCRUnavailable."""
    binary = _compile()
    if binary is None:
        raise OCRUnavailable(
            "Reading text from images needs macOS. Paste the text instead."
        )

    # Vision reads from a file, and the bytes are never persisted beyond this
    # call -- the temp file is removed as soon as recognition finishes.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as handle:
        handle.write(content)
        handle.flush()
        try:
            result = subprocess.run(
                [str(binary), handle.name],
                capture_output=True, timeout=_TIMEOUT_SECONDS, text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise OCRUnavailable("That image took too long to read.") from exc

    if result.returncode != 0:
        raise OCRUnavailable(
            (result.stderr or "That image could not be read.").strip()
        )
    return result.stdout
