"""Stimmprofil und Sprachsteuerung von HOPE.

Die eigentliche Sprachsynthese (TTS) und Spracherkennung (STT) laufen über die
Web Speech API des Browsers – das funktioniert auf Windows-PC und Smartphone
ohne native Zusatzabhängigkeiten und ohne Latenz durch einen Server-Roundtrip.
Dieses Modul verwaltet die Stimmprofile und validiert die Sprachparameter.
"""
from __future__ import annotations

from typing import Any

VOICE_PROFILES: dict[str, dict[str, Any]] = {
    "hope-standard": {
        "id": "hope-standard",
        "label": "HOPE · Standard",
        "description": "Warm, klar und souverän – die Standardstimme.",
        "rate": 1.0,
        "pitch": 1.05,
        "prefer": ["Google", "Anna", "Katja", "female", "Frau"],
    },
    "hope-ruhig": {
        "id": "hope-ruhig",
        "label": "HOPE · Ruhig",
        "description": "Etwas langsamer und tiefer – für konzentriertes Arbeiten.",
        "rate": 0.92,
        "pitch": 1.0,
        "prefer": ["Google", "Katja", "female"],
    },
    "hope-kino": {
        "id": "hope-kino",
        "label": "HOPE · Kino",
        "description": "Cinematisch, betont und ausdrucksstark.",
        "rate": 0.98,
        "pitch": 0.96,
        "prefer": ["Google", "Microsoft", "female"],
    },
}

LANGUAGES = [
    {"code": "de-DE", "label": "Deutsch"},
    {"code": "en-US", "label": "English (US)"},
    {"code": "en-GB", "label": "English (UK)"},
    {"code": "fr-FR", "label": "Français"},
    {"code": "es-ES", "label": "Español"},
    {"code": "it-IT", "label": "Italiano"},
]

ENGINE = {
    "tts": "browser-speech-synthesis",
    "stt": "browser-speech-recognition",
    "note": "Sprachausgabe und -erkennung laufen lokal im Browser (Web Speech API).",
}


def _clamp(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return round(max(low, min(high, number)), 2)


def resolve_voice(settings: dict) -> dict:
    """Führt Stimmprofil und Nutzer-Einstellungen zu einem Sprachprofil zusammen."""
    profile = VOICE_PROFILES.get(str(settings.get("voice_profile")), VOICE_PROFILES["hope-standard"])
    return {
        "profile": profile["id"],
        "label": profile["label"],
        "language": settings.get("language", "de-DE"),
        "rate": _clamp(settings.get("voice_rate"), 0.6, 1.6, profile["rate"]),
        "pitch": _clamp(settings.get("voice_pitch"), 0.7, 1.4, profile["pitch"]),
        "voice_name": str(settings.get("voice_name") or ""),
        "prefer": profile["prefer"],
    }


def bootstrap() -> dict:
    return {
        "engine": ENGINE,
        "profiles": list(VOICE_PROFILES.values()),
        "languages": LANGUAGES,
    }
