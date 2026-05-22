"""Laptop-mic audio capture + Whisper speech-to-text.

Replaces the older ``whisper_stt.py`` and adds a ``record_from_mic`` helper so
Akshita can drive the HRI pipeline from her laptop microphone (instead of
Pepper's onboard mic).

Capture UX
----------
``record_from_mic()`` is press-Enter-to-start / press-Enter-to-stop. It blocks
until the user presses Enter twice, returning WAV bytes ready for ``transcribe``.

STT backends
------------
- ``backend="api"`` (default): OpenAI Whisper-1 via the official SDK. Needs
  ``OPENAI_API_KEY``. Fast, accurate, no model download.
- ``backend="local"``: ``faster-whisper`` (CTranslate2 backend). Free, private,
  works offline. Downloads ~140MB ("base") on first use.
"""

from __future__ import annotations

import asyncio
import io
import os
import wave
from typing import Literal


# ── Mic capture (press Enter to start / Enter to stop) ───────────────────────

def record_from_mic(samplerate: int = 16000, channels: int = 1) -> bytes:
    """Record from the default microphone until the user presses Enter twice.

    Returns 16-bit PCM mono WAV bytes (Whisper-compatible).
    """
    try:
        import sounddevice as sd  # type: ignore[import-untyped]
        import numpy as np  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Mic capture requires 'sounddevice' and 'numpy'.\n"
            "Install with: pip install sounddevice numpy"
        ) from exc

    print("[mic] Press Enter to START recording...", end="", flush=True)
    input()
    print("[mic] Recording... press Enter to STOP.", end="", flush=True)

    chunks: list = []
    stop_flag = {"stop": False}

    def _callback(indata, frames, time_info, status):  # noqa: ANN001
        if not stop_flag["stop"]:
            chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=samplerate, channels=channels, dtype="int16", callback=_callback
    )
    with stream:
        input()  # blocks until Enter
        stop_flag["stop"] = True

    if not chunks:
        return b""

    audio = np.concatenate(chunks, axis=0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


# ── Transcription ────────────────────────────────────────────────────────────

async def transcribe(
    audio_bytes: bytes,
    *,
    backend: Literal["api", "local"] = "api",
    model_size: str = "base",
    language: str | None = None,
) -> tuple[str, str]:
    """Transcribe WAV bytes. Returns ``(text, detected_language)``.

    ``detected_language`` is an ISO 639-1 code or "" when unknown.
    """
    if not audio_bytes:
        return "", ""

    if backend == "api":
        return await _transcribe_api(audio_bytes, language)
    return await asyncio.to_thread(_transcribe_local, audio_bytes, model_size, language)


async def _transcribe_api(
    audio_bytes: bytes, language: str | None
) -> tuple[str, str]:
    try:
        from openai import AsyncOpenAI  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "API Whisper requires 'openai'. Install with: pip install openai"
        ) from exc

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY") or None)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"

    kwargs: dict = {
        "model": "whisper-1",
        "file": audio_file,
        "response_format": "verbose_json",
    }
    if language:
        kwargs["language"] = language

    response = await client.audio.transcriptions.create(**kwargs)
    text = str(getattr(response, "text", "") or "").strip()
    detected = str(getattr(response, "language", "") or "")
    # OpenAI returns full language names ("english") — normalise to ISO codes.
    detected = _normalise_lang(detected)
    return text, detected


def _transcribe_local(
    audio_bytes: bytes, model_size: str, language: str | None
) -> tuple[str, str]:
    try:
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "Local Whisper requires 'faster-whisper'.\n"
            "Install with: pip install faster-whisper"
        ) from exc

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        model = _get_local_model(model_size)
        segments, info = model.transcribe(tmp_path, language=language)
        text = " ".join(seg.text for seg in segments).strip()
        detected = str(getattr(info, "language", "") or "")
        return text, detected
    finally:
        Path(tmp_path).unlink(missing_ok=True)


_LOCAL_MODELS: dict[str, object] = {}


def _get_local_model(model_size: str):
    if model_size not in _LOCAL_MODELS:
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        _LOCAL_MODELS[model_size] = WhisperModel(
            model_size, device="cpu", compute_type="int8"
        )
    return _LOCAL_MODELS[model_size]


def _normalise_lang(name_or_code: str) -> str:
    """OpenAI returns 'english', 'italian', etc. Map to ISO 639-1 codes."""
    if not name_or_code:
        return ""
    s = name_or_code.lower().strip()
    if len(s) == 2:
        return s
    mapping = {
        "english": "en", "italian": "it", "french": "fr", "german": "de",
        "spanish": "es", "portuguese": "pt", "dutch": "nl", "russian": "ru",
        "polish": "pl", "chinese": "zh", "japanese": "ja", "korean": "ko",
        "arabic": "ar", "hindi": "hi", "turkish": "tr", "greek": "el",
        "hebrew": "he", "thai": "th",
    }
    return mapping.get(s, s[:2])
