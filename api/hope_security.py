"""Sicherheitsschicht von HOPE.

- Eingaben werden bereinigt und begrenzt.
- Werkzeug-Argumente werden gegen ihr Schema geprüft.
- Sensible Aktionen benötigen eine ausdrückliche Bestätigung.
- Es gibt keinen Werkzeugweg, der Shell-Befehle oder beliebigen Code ausführt.
"""
from __future__ import annotations

import re
from typing import Any

# Aktionen, die niemals ohne Bestätigung ausgeführt werden.
SENSITIVE_TOOLS: frozenset[str] = frozenset(
    {"delete_task", "delete_note", "delete_reminder", "delete_memory", "save_memory", "delete_conversation"}
)

MAX_USER_TEXT = 6000
MAX_TOOL_STRING = 2000
MAX_JSON_DEPTH = 6
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class SecurityError(ValueError):
    """Ungültige oder nicht erlaubte Eingabe."""


def clean_text(value: Any, limit: int = MAX_USER_TEXT) -> str:
    """Entfernt Steuerzeichen und begrenzt die Länge einer Texteingabe."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SecurityError("Text erwartet.")
    return _CONTROL_CHARS.sub("", value).strip()[:limit]


def mask_secret(text: str, secret: str) -> str:
    """Entfernt versehentlich geloggte Zugangsdaten."""
    if secret and secret in text:
        return text.replace(secret, "***")
    return text


def _check_type(name: str, value: Any, expected: str) -> None:
    if expected == "string":
        if not isinstance(value, str):
            raise SecurityError(f"'{name}' muss Text sein.")
        if len(value) > MAX_TOOL_STRING:
            raise SecurityError(f"'{name}' ist zu lang (max. {MAX_TOOL_STRING} Zeichen).")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise SecurityError(f"'{name}' muss eine ganze Zahl sein.")
    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SecurityError(f"'{name}' muss eine Zahl sein.")
    elif expected == "boolean":
        if not isinstance(value, bool):
            raise SecurityError(f"'{name}' muss wahr oder falsch sein.")
    elif expected == "array":
        if not isinstance(value, list):
            raise SecurityError(f"'{name}' muss eine Liste sein.")
    elif expected == "object":
        if not isinstance(value, dict):
            raise SecurityError(f"'{name}' muss ein Objekt sein.")


def validate_args(schema: dict, args: Any) -> dict:
    """Prüft Werkzeug-Argumente gegen das deklarierte JSON-Schema."""
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise SecurityError("Argumente müssen ein Objekt sein.")

    properties: dict = schema.get("properties", {}) or {}
    required: list = schema.get("required", []) or []

    for name in required:
        if name not in args or args[name] in (None, ""):
            raise SecurityError(f"Pflichtfeld '{name}' fehlt.")

    cleaned: dict[str, Any] = {}
    for name, value in args.items():
        spec = properties.get(name)
        if spec is None:
            continue  # unbekannte Felder werden verworfen
        _check_type(name, value, spec.get("type", "string"))
        if isinstance(value, str):
            value = _CONTROL_CHARS.sub("", value).strip()
        cleaned[name] = value
    return cleaned


def requires_confirmation(tool_name: str) -> bool:
    return tool_name in SENSITIVE_TOOLS
