"""Whisper Speech-to-Text wrapper for OmniLLM / Embodied LLM Arena.

Provides a unified interface for transcribing audio captured by Pepper's
microphone using OpenAI Whisper — either the local ``openai-whisper`` library
(``whisper`` package) or the OpenAI Whisper cloud API.

Architecture context:
    The Pepper robot (Python 2.7 / NAOqi) captures WAV audio and POSTs it via
    HTTP to the AI server (Python 3.x).  The AI server runs this module to
    transcribe the audio before passing the text to the LangGraph agent pipeline.

Two backends are supported:

1. **Local Whisper** (``backend="local"``)
   Uses the ``openai-whisper`` library.  Runs on-device — no API key needed,
   privacy-preserving, but requires a GPU for good performance.
   Install: ``pip install openai-whisper``

2. **OpenAI Whisper API** (``backend="api"``)
   Uses the ``openai`` Python SDK to call the Whisper API endpoint.
   Requires an ``OPENAI_API_KEY`` environment variable.
   Faster on CPU-only servers; small per-minute cost.

Usage::

    stt = WhisperSTT(backend="local", model_size="base")
    text = await stt.transcribe(wav_bytes)
    print(text)   # "Where is Room 305?"

    # Or using the API backend:
    stt = WhisperSTT(backend="api")
    text = await stt.transcribe(wav_bytes, language="fr")
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import Literal


class WhisperSTT:
    """Speech-to-text transcription using OpenAI Whisper.

    Supports local inference (``openai-whisper`` library) and the cloud API.

    Example::

        stt = WhisperSTT(backend="local", model_size="base")
        text = await stt.transcribe(wav_bytes)

        stt_api = WhisperSTT(backend="api")
        text = await stt_api.transcribe(wav_bytes, language="es")
    """

    #: Whisper model sizes available for local inference.
    LOCAL_MODEL_SIZES = ("tiny", "base", "small", "medium", "large", "large-v2", "large-v3")

    def __init__(
        self,
        backend: Literal["local", "api"] = "local",
        model_size: str = "base",
        api_key: str | None = None,
        device: str = "cpu",
    ) -> None:
        """Initialise the Whisper STT wrapper.

        Args:
            backend: ``"local"`` to use the ``openai-whisper`` library, or
                ``"api"`` to use the OpenAI Whisper cloud API.
            model_size: Whisper model size for local inference.
                One of ``"tiny"``, ``"base"``, ``"small"``, ``"medium"``,
                ``"large"``, ``"large-v2"``, ``"large-v3"``.
                Ignored when ``backend="api"``.
            api_key: OpenAI API key.  Defaults to the ``OPENAI_API_KEY``
                environment variable.
            device: PyTorch device for local inference (``"cpu"`` or ``"cuda"``).
        """
        self.backend = backend
        self.model_size = model_size
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.device = device
        self._local_model: object | None = None  # lazily loaded

    # ── Public API ────────────────────────────────────────────────────────────

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
        prompt: str | None = None,
    ) -> str:
        """Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio in WAV, MP3, OGG, FLAC, or M4A format.
            language: Optional ISO 639-1 language hint (e.g. ``"en"``, ``"fr"``).
                When provided, skips language detection and speeds up transcription.
            prompt: Optional text prompt to guide transcription style/vocabulary.

        Returns:
            Transcribed text string.  Returns an empty string on failure.

        Raises:
            ImportError: If the required library is not installed.
        """
        if not audio_bytes:
            return ""

        if self.backend == "local":
            return await asyncio.to_thread(
                self._transcribe_local, audio_bytes, language, prompt
            )
        return await self._transcribe_api(audio_bytes, language, prompt)

    async def transcribe_file(
        self,
        path: str | Path,
        language: str | None = None,
    ) -> str:
        """Transcribe an audio file on disk.

        Args:
            path: Path to an audio file (WAV, MP3, OGG, FLAC, M4A).
            language: Optional ISO 639-1 language hint.

        Returns:
            Transcribed text string.
        """
        audio_bytes = Path(path).read_bytes()
        return await self.transcribe(audio_bytes, language=language)

    # ── Local backend ─────────────────────────────────────────────────────────

    def _load_local_model(self) -> object:
        """Lazily load the Whisper local model.

        Raises:
            ImportError: If ``openai-whisper`` is not installed.
        """
        if self._local_model is None:
            try:
                import whisper  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "Local Whisper requires the 'openai-whisper' package.\n"
                    "Install with: pip install openai-whisper"
                ) from exc
            self._local_model = whisper.load_model(self.model_size, device=self.device)
        return self._local_model

    def _transcribe_local(
        self,
        audio_bytes: bytes,
        language: str | None,
        prompt: str | None,
    ) -> str:
        """Synchronous local Whisper transcription (called via asyncio.to_thread)."""
        model = self._load_local_model()

        # Write bytes to a temp file (Whisper's load_audio expects a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            options: dict = {}
            if language:
                options["language"] = language
            if prompt:
                options["initial_prompt"] = prompt

            result = model.transcribe(tmp_path, **options)  # type: ignore[union-attr]
            return str(result.get("text", "")).strip()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ── API backend ───────────────────────────────────────────────────────────

    async def _transcribe_api(
        self,
        audio_bytes: bytes,
        language: str | None,
        prompt: str | None,
    ) -> str:
        """Call the OpenAI Whisper API asynchronously."""
        try:
            from openai import AsyncOpenAI  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "The OpenAI Whisper API backend requires the 'openai' package.\n"
                "Install with: pip install openai"
            ) from exc

        client = AsyncOpenAI(api_key=self.api_key or None)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"  # OpenAI SDK uses the name to detect format

        kwargs: dict = {"model": "whisper-1", "file": audio_file}
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt

        response = await client.audio.transcriptions.create(**kwargs)
        return str(response.text).strip()

    # ── Utility ───────────────────────────────────────────────────────────────

    @property
    def backend_info(self) -> str:
        """Human-readable description of the active backend configuration."""
        if self.backend == "local":
            return f"Whisper local ({self.model_size}, device={self.device})"
        return "Whisper API (OpenAI cloud)"
