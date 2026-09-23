"""
Text-to-Speech (TTS) Abstraction Layer.

Defines the speak(text: str, lang: Literal["en", "ta"]) interface.
The primary approach is browser-native SpeechSynthesis API on the frontend (kiosk.js),
which operates locally on the client workstation without requiring paid cloud APIs.

Isolated behind an extensible provider interface so offline containerized engines
(e.g., Piper TTS, eSpeak-NG) can be swapped in if needed.
"""

from abc import ABC, abstractmethod
from typing import Literal, Optional, Any


class TTSProvider(ABC):
    """Abstract interface for text-to-speech engines."""

    @abstractmethod
    def synthesize(self, text: str, lang: Literal["en", "ta"] = "en") -> dict[str, Any]:
        """
        Synthesize or package speech instructions.
        :param text: Text string to speak.
        :param lang: Language code ('en' or 'ta').
        :return: TTS metadata or audio payload.
        """
        pass


class BrowserSpeechSynthesisProvider(TTSProvider):
    """
    Browser-native SpeechSynthesis provider.
    Packages text and language tag for client-side window.speechSynthesis execution.
    """

    def synthesize(self, text: str, lang: Literal["en", "ta"] = "en") -> dict[str, Any]:
        target_lang = "ta-IN" if lang == "ta" else "en-US"
        return {
            "mode": "browser_speech_synthesis",
            "text": text.strip(),
            "lang": target_lang,
            "rate": 0.95 if lang == "ta" else 1.0,  # Slightly slower pace for clearer Tamil comprehension
            "pitch": 1.0,
        }


class OfflinePiperTTSStubProvider(TTSProvider):
    """Future offline containerized TTS engine stub."""

    def synthesize(self, text: str, lang: Literal["en", "ta"] = "en") -> dict[str, Any]:
        raise NotImplementedError(
            "Offline containerized TTS (e.g. Piper/eSpeak) is scheduled for future deployment. "
            "Use the browser-native SpeechSynthesis API for current kiosk intake."
        )


_DEFAULT_TTS_PROVIDER: TTSProvider = BrowserSpeechSynthesisProvider()


def speak(
    text: str,
    lang: Literal["en", "ta"] = "en",
    provider: Optional[TTSProvider] = None,
) -> dict[str, Any]:
    """
    Speak interface producing speech synthesis instructions or audio payload.

    :param text: Text string to speak out loud.
    :param lang: Language code ('en' or 'ta').
    :param provider: Specific TTS provider; defaults to BrowserSpeechSynthesisProvider.
    :return: Speech instruction payload suitable for kiosk client execution.
    """
    active_provider = provider or _DEFAULT_TTS_PROVIDER
    return active_provider.synthesize(text=text, lang=lang)
