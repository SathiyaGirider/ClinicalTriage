"""
Speech-to-Text (STT) Abstraction Layer.

Isolates speech recognition behind a clean interface so the current browser-native
Web Speech API client workflow can later be swapped for an offline/containerized
solution (e.g. whisper.cpp, Faster-Whisper) without touching any downstream
extraction, red-flag scanning, follow-up, or confidence logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Union


class SpeechToTextProvider(ABC):
    """
    Abstract interface for speech-to-text engines.
    """

    @abstractmethod
    def transcribe(self, source: Any, language: str = "en") -> str:
        """
        Transcribe audio source or passthrough pre-transcribed text.

        :param source: Audio bytes, filepath, or client-provided transcript text.
        :param language: Language code ('en' or 'ta').
        :return: Clean transcript text.
        """
        pass


class BrowserSpeechPassthroughProvider(SpeechToTextProvider):
    """
    Passthrough provider for transcripts produced client-side via
    browser-native Web Speech API (SpeechRecognition).
    """

    def transcribe(self, source: Union[str, Any], language: str = "en") -> str:
        if isinstance(source, str):
            return source.strip()
        if hasattr(source, "read"):
            content = source.read()
            return content.decode("utf-8", errors="ignore").strip() if isinstance(content, bytes) else str(content).strip()
        return str(source).strip()


class OfflineWhisperStubProvider(SpeechToTextProvider):
    """
    Stub for future containerized/offline STT engine (e.g. whisper.cpp).
    """

    def transcribe(self, source: Any, language: str = "en") -> str:
        raise NotImplementedError(
            "Offline containerized STT (e.g. whisper.cpp) is scheduled for future deployment. "
            "Use the browser-native Web Speech API passthrough for current intake."
        )


_DEFAULT_PROVIDER: SpeechToTextProvider = BrowserSpeechPassthroughProvider()


def get_transcript(
    source: Union[str, Any],
    language: str = "en",
    provider: Optional[SpeechToTextProvider] = None
) -> str:
    """
    Uniform entry point to obtain patient transcript from any source.

    :param source: Raw transcript string or audio payload.
    :param language: Language code ('en' or 'ta').
    :param provider: Specific STT provider implementation; defaults to browser passthrough.
    :return: Sanitized raw transcript string.
    """
    active_provider = provider or _DEFAULT_PROVIDER
    return active_provider.transcribe(source=source, language=language)
