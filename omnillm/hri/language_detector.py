"""Language Detector for multi-lingual HRI routing.

Detects the language of a text input and maps it to the optimal LLM backend
for the Embodied LLM Arena T4 (Multilingual) task type.

Detection approach (in priority order):
1. Unicode script analysis — fast, no external dependencies
2. Statistical n-gram character frequency matching
3. Optional: ``langdetect`` library (higher accuracy, if installed)

Usage::

    detector = LanguageDetector()
    lang, confidence = detector.detect("Bonjour, comment allez-vous?")
    print(lang)        # "fr"
    print(confidence)  # 0.92
    model = detector.get_optimal_model(lang)
    print(model)       # "gemini-flash"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


#: ISO 639-1 -> human-readable language name (used by the multilingual LLM node)
_LANGUAGE_NAME_MAP: dict[str, str] = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
    "pl": "Polish", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "ar": "Arabic", "hi": "Hindi", "tr": "Turkish", "el": "Greek",
    "he": "Hebrew", "th": "Thai", "unknown": "Unknown",
}


@dataclass
class LanguageDetectionResult:
    """Result of language detection.

    Attributes:
        language: ISO 639-1 language code (e.g. ``"en"``, ``"fr"``, ``"ar"``).
        confidence: Detection confidence in [0, 1].
        script: Unicode script category (e.g. ``"Latin"``, ``"Arabic"``, ``"Han"``).
        is_english: Whether the detected language is English.
    """

    language: str
    confidence: float
    script: str = "Latin"
    is_english: bool = True

    @property
    def language_code(self) -> str:
        """Alias for ``language`` (kept for caller compatibility)."""
        return self.language

    @property
    def language_name(self) -> str:
        """Human-readable language name, e.g. ``"French"``."""
        return _LANGUAGE_NAME_MAP.get(self.language, self.language.upper())

    @property
    def recommended_model(self) -> str:
        """OmniLLM model ID best suited to this language (from the static map)."""
        return _LANGUAGE_MODEL_MAP.get(self.language, _LANGUAGE_MODEL_MAP["unknown"])


# Mapping of language code → recommended OmniLLM model for that language.
# Historically non-English languages routed to gemini-flash (strong multilingual,
# cheap). Temporarily routed to openai-gpt4o-mini while the project's Google
# free-tier quota is exhausted (429 RESOURCE_EXHAUSTED). When Gemini access is
# restored, revert the non-"en" entries back to "gemini-flash".
_LANGUAGE_MODEL_MAP: dict[str, str] = {
    # European languages
    "en": "openai-gpt4o-mini",
    "fr": "openai-gpt4o-mini",
    "de": "openai-gpt4o-mini",
    "es": "openai-gpt4o-mini",
    "it": "openai-gpt4o-mini",
    "pt": "openai-gpt4o-mini",
    "nl": "openai-gpt4o-mini",
    "ru": "openai-gpt4o-mini",
    "pl": "openai-gpt4o-mini",
    # Asian languages
    "zh": "openai-gpt4o-mini",
    "ja": "openai-gpt4o-mini",
    "ko": "openai-gpt4o-mini",
    "ar": "openai-gpt4o-mini",
    "hi": "openai-gpt4o-mini",
    "tr": "openai-gpt4o-mini",
    # Default for unknown languages
    "unknown": "openai-gpt4o-mini",
}

# Unicode script → likely language (coarse mapping for script-based detection)
_SCRIPT_LANGUAGE_MAP: dict[str, tuple[str, float]] = {
    "Arabic": ("ar", 0.90),
    "Devanagari": ("hi", 0.88),
    "CJK": ("zh", 0.80),   # Overridden to "ja" or "ko" if confirmed
    "Hiragana": ("ja", 0.95),
    "Katakana": ("ja", 0.95),
    "Hangul": ("ko", 0.95),
    "Cyrillic": ("ru", 0.85),
    "Greek": ("el", 0.90),
    "Hebrew": ("he", 0.90),
    "Thai": ("th", 0.95),
}

# Common non-English high-frequency words for n-gram heuristic
_LANG_WORD_SIGNALS: dict[str, list[str]] = {
    "fr": ["le", "la", "les", "de", "du", "est", "et", "en", "je", "vous", "nous", "une", "bonjour"],
    "de": ["der", "die", "das", "und", "ist", "ich", "sie", "auf", "nicht", "mit", "guten"],
    "es": ["el", "la", "los", "las", "de", "es", "en", "no", "que", "como", "gracias", "hola"],
    "it": ["il", "la", "le", "di", "un", "una", "che", "non", "con", "sono", "ciao", "grazie"],
    "pt": ["o", "a", "os", "as", "de", "em", "que", "não", "com", "como", "olá", "obrigado"],
    "nl": ["de", "het", "een", "van", "is", "dat", "niet", "met", "voor", "hoe", "dag"],
    "ru": ["и", "в", "не", "на", "с", "я", "это", "как", "он", "для", "привет"],
    "zh": ["的", "是", "在", "有", "我", "你", "他", "们", "这", "那"],
    "ja": ["は", "が", "に", "を", "の", "です", "ます", "した", "して"],
    "ko": ["은", "는", "이", "가", "을", "를", "의", "에", "안녕"],
    "ar": ["في", "من", "إلى", "على", "مع", "هذا", "مرحبا"],
    "hi": ["और", "है", "में", "के", "का", "की", "को"],
    "tr": ["ve", "bir", "bu", "de", "da", "ile", "merhaba", "teşekkür"],
}

# Common English stopwords — high frequency signals English
_ENGLISH_SIGNALS: frozenset[str] = frozenset(
    [
        "the", "a", "an", "is", "are", "was", "were", "i", "you", "he", "she",
        "it", "we", "they", "this", "that", "of", "in", "to", "and", "or",
        "but", "for", "with", "have", "has", "do", "does", "can", "could",
        "would", "should", "will", "hello", "hi", "yes", "no", "please",
    ]
)


class LanguageDetector:
    """Detect the language of text and recommend the optimal LLM backend.

    Uses Unicode script analysis as the primary signal (fast, no dependencies),
    with a word-level n-gram heuristic as a secondary signal.  Optionally uses
    the ``langdetect`` library for higher accuracy when installed.

    Example::

        detector = LanguageDetector()
        result = detector.detect("Wo ist das Labor?")
        print(result.language)       # "de"
        print(result.is_english)     # False
        model = detector.get_optimal_model(result.language)
        print(model)                 # "gemini-flash"
    """

    def __init__(
        self,
        custom_model_map: dict[str, str] | None = None,
    ) -> None:
        """Initialise the language detector.

        Args:
            custom_model_map: Optional override for the language → model mapping.
                Keys are ISO 639-1 codes, values are OmniLLM model IDs.
        """
        self._model_map = {**_LANGUAGE_MODEL_MAP, **(custom_model_map or {})}

    def detect(self, text: str) -> LanguageDetectionResult:
        """Detect the language of a text string.

        Args:
            text: Input text (typically a transcribed utterance from Pepper's microphone).

        Returns:
            :class:`LanguageDetectionResult` with language code and confidence.
        """
        if not text or not text.strip():
            return LanguageDetectionResult(
                language="en", confidence=0.5, script="Latin", is_english=True
            )

        # 1. Unicode script analysis (fast, zero dependencies).
        # Threshold 0.80 catches CJK (which is otherwise unrecoverable once
        # we drop substring matching — CJK has no whitespace, so the whole
        # phrase is a single token and word-set membership never hits a
        # 1-char signal like "在").
        script, script_lang, script_conf = self._detect_script(text)
        if script_lang and script_conf >= 0.80:
            return LanguageDetectionResult(
                language=script_lang,
                confidence=script_conf,
                script=script,
                is_english=(script_lang == "en"),
            )

        # 2. Word-level signal matching (word-boundary tokens only).
        # NB: matching `s in text.lower()` (substring) is unsafe — two-letter
        # function words like Spanish "la"/"es"/"en" or Portuguese "o"/"a"
        # appear inside English words ("lab", "does", "open"), which mis-
        # routes plain English to the multilingual model. Only word-boundary
        # hits against the tokenised set count.
        words = set(re.findall(r"\b\w+\b", text.lower()))

        en_hits = len(words & _ENGLISH_SIGNALS)
        best_lang = "en"
        best_score = en_hits
        for lang, signals in _LANG_WORD_SIGNALS.items():
            hits = sum(1 for s in signals if s in words)
            if hits > best_score:
                best_score = hits
                best_lang = lang

        if best_lang == "en":
            if en_hits >= 1:
                confidence = min(0.95, 0.5 + en_hits * 0.05)
                return LanguageDetectionResult(
                    language="en",
                    confidence=confidence,
                    script=script or "Latin",
                    is_english=True,
                )
            langdetect_result = self._try_langdetect(text)
            if langdetect_result:
                return langdetect_result

        confidence = min(0.90, 0.45 + best_score * 0.1)
        return LanguageDetectionResult(
            language=best_lang,
            confidence=confidence,
            script=script or "Latin",
            is_english=(best_lang == "en"),
        )

    def get_optimal_model(self, language: str) -> str:
        """Return the recommended OmniLLM model ID for a given language.

        Args:
            language: ISO 639-1 language code (e.g. ``"fr"``, ``"zh"``).

        Returns:
            OmniLLM model ID string.
        """
        return self._model_map.get(language, self._model_map["unknown"])

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _detect_script(text: str) -> tuple[str, str, float]:
        """Detect the Unicode script of the dominant characters in text.

        Returns:
            Tuple of (script_name, language_code, confidence).
        """
        script_counts: dict[str, int] = {}
        for char in text:
            if char.isalpha():
                try:
                    name = unicodedata.name(char, "")
                    # Extract script from Unicode character name
                    if "ARABIC" in name:
                        script = "Arabic"
                    elif "DEVANAGARI" in name:
                        script = "Devanagari"
                    elif "CJK" in name:
                        script = "CJK"
                    elif "HIRAGANA" in name:
                        script = "Hiragana"
                    elif "KATAKANA" in name:
                        script = "Katakana"
                    elif "HANGUL" in name:
                        script = "Hangul"
                    elif "CYRILLIC" in name:
                        script = "Cyrillic"
                    elif "GREEK" in name:
                        script = "Greek"
                    elif "HEBREW" in name:
                        script = "Hebrew"
                    elif "THAI" in name:
                        script = "Thai"
                    else:
                        script = "Latin"
                    script_counts[script] = script_counts.get(script, 0) + 1
                except Exception:
                    script_counts["Latin"] = script_counts.get("Latin", 0) + 1

        if not script_counts:
            return "Latin", "", 0.0

        dominant = max(script_counts, key=lambda s: script_counts[s])
        total = sum(script_counts.values())
        confidence = script_counts[dominant] / total

        if dominant == "Latin":
            # Latin script — can't determine language from script alone
            return "Latin", "", 0.0

        lang, base_conf = _SCRIPT_LANGUAGE_MAP.get(dominant, ("unknown", 0.7))
        final_conf = min(0.97, base_conf * confidence)
        return dominant, lang, final_conf

    @staticmethod
    def _try_langdetect(text: str) -> LanguageDetectionResult | None:
        """Try using the ``langdetect`` library for high-accuracy detection."""
        try:
            from langdetect import detect_langs  # type: ignore[import-untyped]

            results = detect_langs(text)
            if results:
                top = results[0]
                lang = str(top.lang)
                confidence = float(top.prob)
                return LanguageDetectionResult(
                    language=lang,
                    confidence=confidence,
                    script="Latin",
                    is_english=(lang == "en"),
                )
        except Exception:
            pass
        return None
