"""Schnittstelle zwischen Backend und Benutzeroberfläche.

Stellt zusammen, was die HOPE-Oberfläche beim Start benötigt: Status,
Einstellungen, Stimmprofile, Fähigkeiten und Gesprächsverlauf.
"""
from __future__ import annotations

import config as app_config
import hope_memory
import hope_security as security
import hope_voice

CAPABILITIES = [
    {"id": "chat", "label": "Konversation", "detail": "Gemini-gestützte Dialoge mit Kontext und Gedächtnis."},
    {"id": "voice", "label": "Stimme", "detail": "Sprachausgabe und Spracherkennung im Browser."},
    {"id": "tasks", "label": "Aufgaben", "detail": "Aufgaben, Fristen und Erinnerungen verwalten."},
    {"id": "notes", "label": "Notizen", "detail": "Wissen festhalten und durchsuchen."},
    {"id": "memory", "label": "Gedächtnis", "detail": "Dauerhaft relevante Fakten, nur mit Freigabe."},
    {"id": "tools", "label": "Werkzeuge", "detail": "Rechnen, Wetter, Uhrzeit und Recherche."},
    {"id": "security", "label": "Sicherheit", "detail": "Bestätigungspflicht und Aktionsprotokoll."},
]

_BOOLEAN_KEYS = {
    "tts_enabled", "stt_enabled", "continuous_mode", "wake_word",
    "search_enabled", "tools_enabled", "memory_enabled",
}


def sanitize_settings(patch: dict) -> dict:
    """Akzeptiert nur bekannte Einstellungen in gültigen Wertebereichen."""
    languages = {entry["code"] for entry in hope_voice.LANGUAGES}
    profiles = set(hope_voice.VOICE_PROFILES)
    clean: dict = {}

    for key, value in (patch or {}).items():
        if key not in hope_memory.DEFAULT_SETTINGS:
            continue
        if key in _BOOLEAN_KEYS:
            if isinstance(value, bool):
                clean[key] = value
        elif key == "language":
            if isinstance(value, str) and value in languages:
                clean[key] = value
        elif key == "model":
            if value in app_config.AVAILABLE_MODELS:
                clean[key] = value
        elif key == "voice_profile":
            if value in profiles:
                clean[key] = value
        elif key == "voice_name":
            if isinstance(value, str):
                clean[key] = security.clean_text(value, 120)
        elif key in {"voice_rate", "voice_pitch"}:
            low, high = (0.6, 1.6) if key == "voice_rate" else (0.7, 1.4)
            try:
                clean[key] = round(max(low, min(high, float(value))), 2)
            except (TypeError, ValueError):
                continue
    return clean


def status(cfg: app_config.Config, memory: hope_memory.HopeMemory, tools) -> dict:
    settings = memory.get_settings()
    return {
        "name": app_config.APP_NAME,
        "subtitle": app_config.APP_SUBTITLE,
        "gemini": cfg.gemini_ready,
        "model": settings.get("model", cfg.model),
        "conversations": len(memory.list_conversations(limit=200)),
        "tools": len(tools.tools),
        "research": bool(settings.get("search_enabled", True)),
        "memory_entries": len(memory.list_memories(limit=500)),
    }


def bootstrap(cfg: app_config.Config, memory: hope_memory.HopeMemory, tools) -> dict:
    settings = memory.get_settings()
    return {
        "app": {
            "name": app_config.APP_NAME,
            "subtitle": app_config.APP_SUBTITLE,
            "version": "1.0",
        },
        "status": status(cfg, memory, tools),
        "settings": settings,
        "models": app_config.AVAILABLE_MODELS,
        "voice": hope_voice.bootstrap(),
        "voice_profile": hope_voice.resolve_voice(settings),
        "capabilities": CAPABILITIES,
        "tools": sorted(tools.tools),
        "conversations": memory.list_conversations(),
    }
