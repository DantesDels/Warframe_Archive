"""Extension and content policy for security scanning."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

SCRIPT_EXTENSIONS = {
    ".bat", ".cmd", ".com", ".cpl", ".exe", ".gadget", ".hta", ".inf",
    ".jar", ".js", ".jse", ".lnk", ".msc", ".msi", ".msp", ".pif", ".ps1",
    ".psd1", ".psm1", ".reg", ".scf", ".scr", ".sh", ".url", ".vb", ".vbe",
    ".vbs", ".ws", ".wsc", ".wsf", ".wsh",
}
MACRO_EXTENSIONS = {
    ".docm", ".dotm", ".potm", ".ppam", ".pptm", ".sldm", ".xlam", ".xlsb",
    ".xlsm", ".xltm",
}
ACTIVE_EXTENSIONS = {".htm", ".html", ".pdf", ".svg", ".xml", ".xhtml"}
ARCHIVE_EXTENSIONS = {
    ".7z", ".bz2", ".cab", ".gz", ".iso", ".rar", ".tar", ".xz", ".zip",
}
IMAGE_EXTENSIONS = {
    ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp",
}
RISKY_FORMAT_EXTENSIONS = {".apk", ".app", ".dll", ".dmg", ".so"}


def classify_suffix(suffix: str) -> tuple[str, str] | None:
    """Return (code, reason) when the extension is blocked, else None."""
    ext = suffix.lower()
    if ext in SCRIPT_EXTENSIONS or ext in RISKY_FORMAT_EXTENSIONS:
        return "blocked_script", (
            "Fichier exécutable, script ou format à risque bloqué."
        )
    if ext in MACRO_EXTENSIONS:
        return "blocked_macro", (
            "Document avec macros bloqué (risque d'élévation de privilèges)."
        )
    if ext in ACTIVE_EXTENSIONS:
        return "blocked_active_content", (
            "Contenu actif ou potentiellement scripté bloqué par sécurité."
        )
    if ext in ARCHIVE_EXTENSIONS:
        return "blocked_archive", (
            "Archive bloquée (contenu imbriqué potentiellement dangereux)."
        )
    if ext in IMAGE_EXTENSIONS:
        return "blocked_image_qr_check", (
            "Image bloquée : analyse des codes QR requise avant import."
        )
    return None


def path_suffix(location: str) -> str:
    """Extract a normalized suffix from a local path or URL path component."""
    value = (location or "").strip()
    if value.lower().startswith(("http://", "https://")):
        return Path(urlparse(value).path).suffix.lower()
    return Path(value).suffix.lower()
