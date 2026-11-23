"""Bounded ASR transcription for audio and video files."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from .guards import enforce_duration_limit, probe_media_duration_seconds

AsrBackend = Callable[[bytes, str], str]


def transcribe_media(
    raw: bytes,
    *,
    ext: str = ".wav",
    max_media_minutes: int = 30,
    duration_override: float | None = None,
    backend: AsrBackend | None = None,
) -> tuple[str, str, float]:
    """Transcribe audio/video under strict duration cap; returns (text, engine, sec)."""
    duration = (
        float(duration_override)
        if duration_override is not None
        else probe_media_duration_seconds(raw, ext=ext)
    )
    enforce_duration_limit(duration, max_media_minutes)
    if backend is not None:
        return str(backend(raw, ext) or "").strip(), "custom_asr", duration
    text, engine = _try_whisper_backends(raw, ext)
    return text, engine, duration


def _try_whisper_backends(raw: bytes, ext: str) -> tuple[str, str]:
    suffix = ext if ext.startswith(".") else f".{ext or 'wav'}"
    tmp = Path(tempfile.gettempdir()) / f"atelier_v1_asr{suffix}"
    try:
        tmp.write_bytes(raw)
        try:
            from faster_whisper import WhisperModel  # type: ignore

            model = WhisperModel("tiny", compute_type="int8")
            segments, _info = model.transcribe(str(tmp))
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return text, "faster_whisper"
        except Exception:  # noqa: BLE001
            pass
        try:
            import whisper  # type: ignore

            model = whisper.load_model("tiny")
            result = model.transcribe(str(tmp))
            return str(result.get("text", "")).strip(), "whisper"
        except Exception:  # noqa: BLE001
            return "", "asr_unavailable"
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
