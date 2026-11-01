"""Werkzeuge und Integrationen von HOPE.

Jedes Werkzeug hat ein JSON-Schema, eine Handler-Funktion und – bei sensiblen
Aktionen – eine Bestätigungspflicht. Es existiert bewusst kein Werkzeug, das
Shell-Befehle oder beliebigen Code ausführt.
"""
from __future__ import annotations

import ast
import json
import math
import operator
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

import httpx

import hope_security as security
from hope_memory import HopeMemory

Handler = Callable[[dict], Awaitable[str]]

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

WEATHER_CODES = {
    0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bedeckt",
    45: "neblig", 48: "Reifnebel", 51: "leichter Nieselregen", 53: "Nieselregen",
    55: "starker Nieselregen", 56: "gefrierender Nieselregen", 57: "starker gefrierender Nieselregen",
    61: "leichter Regen", 63: "Regen", 65: "starker Regen", 66: "gefrierender Regen",
    67: "starker gefrierender Regen", 71: "leichter Schneefall", 73: "Schneefall",
    75: "starker Schneefall", 77: "Schneegriesel", 80: "leichte Regenschauer",
    81: "Regenschauer", 82: "heftige Regenschauer", 85: "Schneeschauer", 86: "starke Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "schweres Gewitter mit Hagel",
}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Handler


def _obj(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


# ----------------------------------------------------------------- Rechnen
_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp,
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil,
}
_CONSTS = {"pi": math.pi, "e": math.e}


def safe_calculate(expression: str) -> float:
    """Werter einen arithmetischen Ausdruck ohne eval() aus."""
    if len(expression) > 200:
        raise ValueError("Ausdruck ist zu lang.")
    tree = ast.parse(expression, mode="eval")

    def walk(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 500:
                raise ValueError("Exponent zu groß.")
            return _BINOPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](walk(node.operand))
        if isinstance(node, ast.Name) and node.id in _CONSTS:
            return _CONSTS[node.id]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS
            and not node.keywords
        ):
            return _FUNCS[node.func.id](*[walk(arg) for arg in node.args])
        raise ValueError("Nicht erlaubter Ausdruck.")

    return float(walk(tree))


class ToolRegistry:
    """Registry aller Werkzeuge inklusive Bestätigungslogik."""

    def __init__(self, memory: HopeMemory, research: Callable[[str], Awaitable[str]] | None = None) -> None:
        self.memory = memory
        self._research = research
        handlers: list[Tool] = [
            Tool(
                "get_datetime",
                "Aktuelles Datum, Uhrzeit und Wochentag.",
                _obj({}),
                self._get_datetime,
            ),
            Tool(
                "create_task",
                "Legt eine Aufgabe oder Erinnerung mit optionaler Fälligkeit an.",
                _obj(
                    {
                        "title": {"type": "string", "description": "Kurzer Aufgabentitel."},
                        "notes": {"type": "string", "description": "Optionale Details."},
                        "due_at": {"type": "string", "description": "Fälligkeit als ISO-String, z. B. 2026-11-02T09:00."},
                        "priority": {"type": "string", "description": "niedrig, mittel oder hoch."},
                    },
                    ["title"],
                ),
                self._create_task,
            ),
            Tool(
                "list_tasks",
                "Listet Aufgaben des Nutzers auf.",
                _obj({"status": {"type": "string", "description": "open, done oder all."}}),
                self._list_tasks,
            ),
            Tool(
                "complete_task",
                "Markiert eine Aufgabe als erledigt.",
                _obj({"task_id": {"type": "integer", "description": "ID der Aufgabe."}}, ["task_id"]),
                self._complete_task,
            ),
            Tool(
                "delete_task",
                "Löscht eine Aufgabe dauerhaft (bestätigungspflichtig).",
                _obj({"task_id": {"type": "integer", "description": "ID der Aufgabe."}}, ["task_id"]),
                self._delete_task,
            ),
            Tool(
                "create_note",
                "Erstellt eine Notiz.",
                _obj(
                    {
                        "title": {"type": "string", "description": "Titel der Notiz."},
                        "body": {"type": "string", "description": "Inhalt der Notiz."},
                    },
                    ["title"],
                ),
                self._create_note,
            ),
            Tool(
                "list_notes",
                "Sucht Notizen nach Stichwort.",
                _obj({"query": {"type": "string", "description": "Suchbegriff, leer für alle Notizen."}}),
                self._list_notes,
            ),
            Tool(
                "delete_note",
                "Löscht eine Notiz dauerhaft (bestätigungspflichtig).",
                _obj({"note_id": {"type": "integer", "description": "ID der Notiz."}}, ["note_id"]),
                self._delete_note,
            ),
            Tool(
                "create_reminder",
                "Legt eine zeitgebundene Erinnerung an.",
                _obj(
                    {
                        "text": {"type": "string", "description": "Woran soll erinnert werden?"},
                        "remind_at": {"type": "string", "description": "Zeitpunkt als ISO-String."},
                    },
                    ["text", "remind_at"],
                ),
                self._create_reminder,
            ),
            Tool(
                "delete_reminder",
                "Löscht eine Erinnerung (bestätigungspflichtig).",
                _obj({"reminder_id": {"type": "integer", "description": "ID der Erinnerung."}}, ["reminder_id"]),
                self._delete_reminder,
            ),
            Tool(
                "save_memory",
                "Speichert eine dauerhaft wichtige Information über den Nutzer im Gedächtnis (bestätigungspflichtig).",
                _obj(
                    {
                        "content": {"type": "string", "description": "Die zu merkende Information."},
                        "category": {"type": "string", "description": "fakt, vorliebe, projekt oder notiz."},
                    },
                    ["content"],
                ),
                self._save_memory,
            ),
            Tool(
                "list_memories",
                "Listet die gespeicherten Gedächtniseinträge auf.",
                _obj({}),
                self._list_memories,
            ),
            Tool(
                "calculate",
                "Berechnet einen mathematischen Ausdruck.",
                _obj({"expression": {"type": "string", "description": "z. B. (12*7)+sqrt(81)"}}, ["expression"]),
                self._calculate,
            ),
            Tool(
                "get_weather",
                "Aktuelles Wetter und Vorhersage für einen Ort.",
                _obj(
                    {
                        "city": {"type": "string", "description": "Stadtname, z. B. Berlin."},
                        "days": {"type": "integer", "description": "Anzahl der Vorhersagetage 1-5."},
                    },
                    ["city"],
                ),
                self._get_weather,
            ),
            Tool(
                "web_research",
                "Recherchiert aktuelle Informationen im Internet (nur wenn aktiviert).",
                _obj({"query": {"type": "string", "description": "Suchanfrage."}}, ["query"]),
                self._web_research,
            ),
        ]
        self.tools: dict[str, Tool] = {tool.name: tool for tool in handlers}

    # ------------------------------------------------------------ Metadaten
    def set_research(self, research: Callable[[str], Awaitable[str]]) -> None:
        """Verknüpft die Recherche-Funktion des Brains (vermeidet Zirkelimporte)."""
        self._research = research

    @property
    def research_available(self) -> bool:
        return self._research is not None

    def declarations(self, include_research: bool = True) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self.tools.values()
            if t.name != "web_research" or include_research
        ]

    # ----------------------------------------------------------- Ausführung
    def _summary(self, name: str, args: dict) -> str:
        if name == "delete_task":
            return f"Aufgabe #{args.get('task_id')} löschen"
        if name == "delete_note":
            return f"Notiz #{args.get('note_id')} löschen"
        if name == "delete_reminder":
            return f"Erinnerung #{args.get('reminder_id')} löschen"
        if name == "save_memory":
            return f"Im Gedächtnis speichern: „{str(args.get('content', ''))[:120]}“"
        return name

    def _label(self, name: str, args: dict) -> str:
        labels = {
            "get_datetime": "Uhrzeit geprüft",
            "create_task": "Aufgabe angelegt",
            "list_tasks": "Aufgaben gelesen",
            "complete_task": "Aufgabe erledigt",
            "delete_task": "Aufgabe gelöscht",
            "create_note": "Notiz erstellt",
            "list_notes": "Notizen durchsucht",
            "delete_note": "Notiz gelöscht",
            "create_reminder": "Erinnerung gesetzt",
            "delete_reminder": "Erinnerung gelöscht",
            "save_memory": "Gedächtnis aktualisiert",
            "list_memories": "Gedächtnis gelesen",
            "calculate": "Berechnung ausgeführt",
            "get_weather": "Wetterdaten abgerufen",
            "web_research": "Recherche durchgeführt",
        }
        return labels.get(name, name)

    async def execute(self, name: str, args: Any, conversation_id: int | None = None) -> dict:
        tool = self.tools.get(name)
        if tool is None:
            self.memory.log_action(name, "unbekanntes Werkzeug", status="fehler")
            return {"status": "fehler", "result": f"Unbekanntes Werkzeug: {name}", "label": "Unbekanntes Werkzeug"}

        try:
            clean = security.validate_args(tool.parameters, args)
        except security.SecurityError as exc:
            return {"status": "fehler", "result": f"Ungültige Argumente: {exc}", "label": "Ungültige Eingabe"}

        if security.requires_confirmation(name):
            summary = self._summary(name, clean)
            pending_id = self.memory.create_pending(name, clean, summary, conversation_id)
            self.memory.log_action(name, summary, status="bestaetigung_noetig", sensitive=True)
            return {
                "status": "bestaetigung",
                "pending_id": pending_id,
                "summary": summary,
                "label": summary,
                "result": (
                    "Diese Aktion ist bestätigungspflichtig und wartet auf die Entscheidung des Nutzers. "
                    "Erkläre ihm kurz, was du tun möchtest, und fordere ihn auf, die Aktion zu bestätigen oder abzulehnen."
                ),
            }

        try:
            result = await tool.handler(clean)
        except Exception as exc:  # Werkzeugfehler dürfen den Chat nicht abbrechen
            self.memory.log_action(name, f"{type(exc).__name__}: {exc}", status="fehler")
            return {"status": "fehler", "result": f"Fehler bei {name}: {exc}", "label": "Fehler"}
        self.memory.log_action(name, json.dumps(clean, ensure_ascii=False)[:1000])
        return {"status": "ok", "result": result, "label": self._label(name, clean)}

    async def run_confirmed(self, action: dict) -> str:
        """Führt eine zuvor bestätigte, sensible Aktion aus."""
        tool = self.tools.get(action["tool"])
        if tool is None:
            raise RuntimeError("Werkzeug nicht gefunden.")
        result = await tool.handler(action["args"])
        self.memory.log_action(action["tool"], action.get("summary", ""), status="bestaetigt", sensitive=True)
        return result

    # ------------------------------------------------------------- Handler
    async def _get_datetime(self, _args: dict) -> str:
        now = datetime.now().astimezone()
        return f"{WEEKDAYS[now.weekday()]}, {now.strftime('%d.%m.%Y')} – {now.strftime('%H:%M')} Uhr ({now.tzname()})."

    async def _create_task(self, args: dict) -> str:
        title = args["title"]
        priority = (args.get("priority") or "mittel").lower()
        if priority not in {"niedrig", "mittel", "hoch"}:
            priority = "mittel"
        task_id = self.memory.add_task(
            title=title, notes=args.get("notes", ""), due_at=args.get("due_at"), priority=priority
        )
        due = f", fällig {args['due_at']}" if args.get("due_at") else ""
        return f"Aufgabe #{task_id} angelegt: „{title}“ (Priorität {priority}{due})."

    async def _list_tasks(self, args: dict) -> str:
        status = (args.get("status") or "open").lower()
        if status not in {"open", "done", "all"}:
            status = "open"
        tasks = self.memory.list_tasks(status=status)
        if not tasks:
            return "Es sind keine passenden Aufgaben gespeichert."
        lines = [
            f"#{t['id']} [{'x' if t['done'] else ' '}] {t['title']} (Priorität {t['priority']}"
            + (f", fällig {t['due_at']}" if t["due_at"] else "")
            + ")"
            for t in tasks[:25]
        ]
        return "Aufgaben:\n" + "\n".join(lines)

    async def _complete_task(self, args: dict) -> str:
        if self.memory.complete_task(int(args["task_id"])):
            return f"Aufgabe #{args['task_id']} ist als erledigt markiert."
        return f"Aufgabe #{args['task_id']} wurde nicht gefunden."

    async def _delete_task(self, args: dict) -> str:
        if self.memory.delete_task(int(args["task_id"])):
            return f"Aufgabe #{args['task_id']} wurde gelöscht."
        return f"Aufgabe #{args['task_id']} wurde nicht gefunden."

    async def _create_note(self, args: dict) -> str:
        note_id = self.memory.add_note(args["title"], args.get("body", ""))
        return f"Notiz #{note_id} „{args['title']}“ gespeichert."

    async def _list_notes(self, args: dict) -> str:
        notes = self.memory.list_notes(args.get("query", ""))
        if not notes:
            return "Keine Notizen gefunden."
        lines = [f"#{n['id']} {n['title']}: {n['body'][:200]}" for n in notes[:15]]
        return "Notizen:\n" + "\n".join(lines)

    async def _delete_note(self, args: dict) -> str:
        if self.memory.delete_note(int(args["note_id"])):
            return f"Notiz #{args['note_id']} wurde gelöscht."
        return f"Notiz #{args['note_id']} wurde nicht gefunden."

    async def _create_reminder(self, args: dict) -> str:
        reminder_id = self.memory.add_reminder(args["text"], args["remind_at"])
        return f"Erinnerung #{reminder_id} für {args['remind_at']} gespeichert: „{args['text']}“."

    async def _delete_reminder(self, args: dict) -> str:
        if self.memory.delete_reminder(int(args["reminder_id"])):
            return f"Erinnerung #{args['reminder_id']} wurde gelöscht."
        return f"Erinnerung #{args['reminder_id']} wurde nicht gefunden."

    async def _save_memory(self, args: dict) -> str:
        category = (args.get("category") or "notiz").lower()
        if category not in {"fakt", "vorliebe", "projekt", "notiz"}:
            category = "notiz"
        memory_id = self.memory.add_memory(args["content"], category)
        return f"Im Gedächtnis gespeichert (#{memory_id}, {category}): {args['content']}"

    async def _list_memories(self, _args: dict) -> str:
        memories = self.memory.list_memories()
        if not memories:
            return "Das Gedächtnis ist noch leer."
        return "Gedächtnis:\n" + "\n".join(
            f"#{m['id']} ({m['category']}) {m['content']}" for m in memories[:30]
        )

    async def _calculate(self, args: dict) -> str:
        value = safe_calculate(args["expression"])
        if value == int(value):
            return f"{args['expression']} = {int(value)}"
        return f"{args['expression']} = {round(value, 6)}"

    async def _get_weather(self, args: dict) -> str:
        city = args["city"].strip()
        days = max(1, min(int(args.get("days") or 1), 5))
        async with httpx.AsyncClient(timeout=15) as client:
            geo = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "de", "format": "json"},
            )
            results = (geo.json() or {}).get("results") or []
            if not results:
                return f"Ich konnte keinen Ort namens „{city}“ finden."
            place = results[0]
            forecast = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,wind_speed_10m,weather_code",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                    "timezone": "auto",
                    "forecast_days": days,
                },
            )
            data = forecast.json()

        current = data.get("current") or {}
        label = f"{place['name']}, {place.get('country', '')}".strip(", ")
        parts = [
            f"Wetter in {label}: {WEATHER_CODES.get(current.get('weather_code'), 'unbekannt')}, "
            f"{round(current.get('temperature_2m', 0))} °C, Wind {round(current.get('wind_speed_10m', 0))} km/h."
        ]
        daily = data.get("daily") or {}
        for index, date in enumerate(daily.get("time", [])[:days]):
            parts.append(
                f"{date}: {WEATHER_CODES.get(daily['weather_code'][index], 'unbekannt')}, "
                f"{round(daily['temperature_2m_min'][index])}–{round(daily['temperature_2m_max'][index])} °C."
            )
        return " ".join(parts)

    async def _web_research(self, args: dict) -> str:
        if self._research is None:
            return "Die Internet-Recherche ist in den Einstellungen deaktiviert."
        return await self._research(args["query"])


def describe_next_reminder(memory: HopeMemory) -> str | None:
    """Kleine Hilfe für den Systemprompt: nächste anstehende Erinnerung."""
    open_reminders = memory.list_reminders(only_open=True)
    if not open_reminders:
        return None
    try:
        moment = datetime.fromisoformat(open_reminders[0]["remind_at"])
    except ValueError:
        return open_reminders[0]["text"]
    delta = moment - datetime.now(moment.tzinfo) if moment.tzinfo else moment - datetime.now()
    minutes = int(delta.total_seconds() // 60)
    return f"{open_reminders[0]['text']} (in {minutes} Minuten)" if minutes > 0 else open_reminders[0]["text"]
