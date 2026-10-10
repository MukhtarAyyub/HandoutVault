"""
materials.validators
=====================
File upload validation for Material.file — see materials/models.py's
own docstring for why this lives as a model-field validator rather than
form-level logic (short version: it then applies identically whether a
Material is created through the upload form, the Django admin, or a
script).

Two layers, both required to pass, checked cheapest-first:

  1. Extension whitelist + size limit.
  2. Content verification (SECURITY.md, "Restrict file uploads"): the
     file's actual bytes are inspected to confirm they match what the
     extension claims, using only the Python standard library (no new
     dependency, no system package like libmagic to install). A
     renamed `virus.exe` saved as `lecture.pdf` is rejected here even
     though its extension alone would pass layer 1.

This is deliberately not the only line of defence. See
materials.views.material_download (serves every file with
Content-Disposition: attachment, so a browser is never asked to "run"
one in-place) and SECURITY.md more generally — validation reduces risk,
it doesn't make an uploaded file trusted.
"""
import os
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".xlsx", ".txt"}

# The one internal path each OOXML format is guaranteed to contain —
# this is what actually tells a .docx apart from a .pptx/.xlsx once we
# already know it's a real zip (all three share the same outer ZIP
# magic bytes, so the magic bytes alone can't distinguish them).
_OOXML_MARKERS = {
    ".docx": "word/document.xml",
    ".pptx": "ppt/presentation.xml",
    ".xlsx": "xl/workbook.xml",
}


def _read_prefix(file, num_bytes=8):
    """Peek at the first `num_bytes` without disturbing the upload for the save that follows."""
    file.seek(0)
    prefix = file.read(num_bytes)
    file.seek(0)
    return prefix


def _looks_like_pdf(file) -> bool:
    return _read_prefix(file, 5) == b"%PDF-"


def _looks_like_ooxml(file, ext) -> bool:
    """True if `file` is a real ZIP archive containing the marker file `ext` requires."""
    if _read_prefix(file, 4) != b"PK\x03\x04":
        return False
    file.seek(0)
    try:
        # Pass the upload object itself (not file.read() into a buffer) —
        # zipfile only needs to seek to the central directory near the
        # end, so this avoids loading a potentially 100 MB upload fully
        # into memory just to validate it.
        with zipfile.ZipFile(file) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return False
    finally:
        file.seek(0)
    return "[Content_Types].xml" in names and _OOXML_MARKERS[ext] in names


def _looks_like_text(file) -> bool:
    """
    Heuristic only — there's no magic-byte signature for "plain text" to
    check against. Good enough to catch a binary file wearing a `.txt`
    extension: real text has no NUL bytes and decodes cleanly as UTF-8.
    """
    sample = _read_prefix(file, 4096)
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def validate_material_file(file):
    """
    Reject disallowed extensions, oversized uploads, and files whose
    actual content doesn't match their extension — cheapest checks
    first, so a huge disallowed file fails fast without being scanned.
    """
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValidationError(f"Unsupported file type '{ext}'. Allowed types: {allowed}.")

    max_mb = getattr(settings, "MAX_MATERIAL_UPLOAD_MB", 100)
    max_bytes = max_mb * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(f"File too large ({file.size / (1024 * 1024):.1f} MB). Maximum is {max_mb} MB.")

    if ext == ".pdf":
        content_ok = _looks_like_pdf(file)
    elif ext == ".txt":
        content_ok = _looks_like_text(file)
    else:
        content_ok = _looks_like_ooxml(file, ext)

    if not content_ok:
        raise ValidationError(
            f"This file doesn't look like a valid {ext} file — its contents don't match its "
            "extension. Re-export or re-save it and try again."
        )
