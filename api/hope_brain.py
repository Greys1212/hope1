"""HOPE-Brain – die Gemini-Intelligenz hinter der Konversation.

Aufgaben:
- Systemprompt aus Persona, Gedächtnis und Kontext bauen
- Streaming-Antworten von der Gemini-API (SSE) durchreichen
- Werkzeugaufrufe ausführen und deren Ergebnisse zurückgeben
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, AsyncIterator

import httpx

import config as app_config
import hope_security as security
from hope_memory import HopeMemory
from hope_tools import ToolRegistry, describe_next_reminder

WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

NO_KEY_MESSAGE = (
    "Mir fehlt noch der Zugang zu meiner Intelligenz: Es ist kein Gemini-API-Schlüssel hinterlegt. "
    "Sobald GEMINI_API_KEY als Secret gesetzt ist, bin ich vollständig einsatzbereit."
)


class HopeBrainError(RuntimeError):
    """Fehler bei der Kommunikation mit dem Gemini-Dienst."""


class HopeBrain:
    def __init__(self, cfg: app_config.Config, memory: HopeMemory, tools: ToolRegistry) -> None:
        self.cfg = cfg
        self.memory = memory
        self.tools = tools

    @property
    def ready(self) -> bool:
        return self.cfg.gemini_ready

    # ------------------------------------------------------------- Öffentlich
    async def stream_reply(
        self,
        conversation_id: int,
        settings: dict,
        attachments: list[dict] | None = None,
    ) -> AsyncIterator[dict]:
        """Streamt die Antwort als Ereignisse: delta, tool, confirm, error."""
        if not self.ready:
            yield {"type": "error", "message": NO_KEY_MESSAGE}
            return

        model = self._model(settings)
        contents = self._contents(conversation_id)
        self._attach(contents, attachments or [])

        declarations: list[dict] = []
        if settings.get("tools_enabled", True):
            declarations = self.tools.declarations(
                include_research=bool(settings.get("search_enabled", True)) and self.tools.research_available
            )

        for round_index in range(self.cfg.max_tool_rounds + 1):
            body = self._body(model, contents, settings, declarations)
            model_parts: list[dict] = []
            function_calls: list[dict] = []
            text_seen = 0

            try:
                async for chunk in self._stream_chunks(model, body):
                    for candidate in chunk.get("candidates") or []:
                        for part in (candidate.get("content") or {}).get("parts") or []:
                            if part.get("thought"):
                                continue
                            text = part.get("text")
                            if text:
                                model_parts.append({"text": text})
                                text_seen += len(text)
                                yield {"type": "delta", "text": text}
                            if "functionCall" in part:
                                model_parts.append({"functionCall": part["functionCall"]})
                                function_calls.append(part["functionCall"])
            except HopeBrainError as exc:
                yield {"type": "error", "message": str(exc)}
                return
            except httpx.HTTPError as exc:
                yield {"type": "error", "message": f"Verbindung zum Gemini-Dienst fehlgeschlagen: {type(exc).__name__}"}
                return

            if not function_calls:
                if text_seen == 0 and round_index == 0:
                    yield {
                        "type": "error",
                        "message": "Dazu konnte ich keine Antwort erzeugen. Formuliere die Anfrage bitte etwas anders.",
                    }
                return

            contents.append({"role": "model", "parts": model_parts})
            response_parts: list[dict] = []
            for call in function_calls:
                name = str(call.get("name") or "")
                args = call.get("args") or {}
                yield {"type": "tool", "name": name, "status": "laeuft", "label": name}
                outcome = await self.tools.execute(name, args, conversation_id=conversation_id)
                yield {
                    "type": "tool",
                    "name": name,
                    "status": "fertig",
                    "state": outcome["status"],
                    "label": outcome.get("label", name),
                }
                if outcome["status"] == "bestaetigung":
                    yield {
                        "type": "confirm",
                        "id": outcome["pending_id"],
                        "tool": name,
                        "summary": outcome["summary"],
                    }
                response_parts.append(
                    {"functionResponse": {"name": name, "response": {"result": outcome["result"]}}}
                )
            contents.append({"role": "user", "parts": response_parts})

        yield {
            "type": "delta",
            "text": "\n\nIch habe die maximale Anzahl an Werkzeugschritten erreicht. Sag mir bitte, wie ich fortfahren soll.",
        }

    async def research(self, query: str) -> str:
        """Recherche über die Google-Search-Grounding-Funktion von Gemini."""
        if not self.ready:
            return "Die Recherche benötigt einen Gemini-API-Schlüssel."
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "Recherchiere im Web: " + query + "\n"
                                "Fasse die wichtigsten, aktuellen Fakten auf Deutsch in höchstens 8 Sätzen zusammen "
                                "und nenne die Quellen (Domain genügt)."
                            )
                        }
                    ],
                }
            ],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 900},
        }
        url = f"{app_config.GEMINI_ENDPOINT}/models/{self.cfg.model}:generateContent"
        headers = {"x-goog-api-key": self.cfg.gemini_api_key, "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.cfg.request_timeout, connect=15.0)) as client:
            response = await client.post(url, headers=headers, json=body)
        if response.status_code >= 400:
            raise self._api_error(response.status_code, response.content)
        payload = response.json()
        parts = ((payload.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
        return text or "Die Recherche hat keine verwertbaren Ergebnisse geliefert."

    # -------------------------------------------------------------- Interna
    def _model(self, settings: dict) -> str:
        model = str(settings.get("model") or self.cfg.model)
        return model if model in app_config.AVAILABLE_MODELS else app_config.DEFAULT_MODEL

    def _contents(self, conversation_id: int) -> list[dict]:
        messages = self.memory.list_messages(conversation_id, limit=self.cfg.max_history_messages)
        contents: list[dict] = []
        for message in messages:
            role = message["role"]
            if role not in {"user", "assistant", "system"}:
                continue
            api_role = "user" if role in {"user", "system"} else "model"
            text = message["content"] if role != "system" else f"(Systemhinweis: {message['content']})"
            if not text.strip():
                continue
            if contents and contents[-1]["role"] == api_role:
                contents[-1]["parts"].append({"text": text})
            else:
                contents.append({"role": api_role, "parts": [{"text": text}]})
        return contents

    def _attach(self, contents: list[dict], attachments: list[dict]) -> None:
        if not attachments or not contents:
            return
        target = next((item for item in reversed(contents) if item["role"] == "user"), None)
        if target is None:
            return
        for attachment in attachments:
            if not attachment.get("data"):
                continue
            target["parts"].append(
                {
                    "inlineData": {
                        "mimeType": attachment.get("mime_type") or "application/octet-stream",
                        "data": attachment["data"],
                    }
                }
            )
            target["parts"].append({"text": f"(Angehängte Datei: {attachment.get('name') or 'Datei'})"})

    def _system_prompt(self, settings: dict) -> str:
        now = datetime.now().astimezone()
        blocks = [
            app_config.PERSONA_PROMPT,
            (
                "KONTEXT\n"
                f"- Jetzt: {WEEKDAYS_DE[now.weekday()]}, {now.strftime('%d.%m.%Y')}, "
                f"{now.strftime('%H:%M')} Uhr ({now.tzname()})."
            ),
        ]

        if settings.get("memory_enabled", True):
            memories = self.memory.list_memories(limit=40)
            if memories:
                blocks.append(
                    "GEDÄCHTNIS (vom Nutzer freigegeben)\n"
                    + "\n".join(f"- ({m['category']}) {m['content']}" for m in memories)
                )
            next_reminder = describe_next_reminder(self.memory)
            if next_reminder:
                blocks.append(f"NÄCHSTE ERINNERUNG\n- {next_reminder}")

        open_tasks = self.memory.list_tasks(status="open")
        if open_tasks:
            blocks.append(
                f"OFFENE AUFGABEN: {len(open_tasks)}\n"
                + "\n".join(f"- #{t['id']} {t['title']}" for t in open_tasks[:8])
            )

        if settings.get("tools_enabled", True):
            blocks.append(
                "WERKZEUGE\n"
                "- Nutze Werkzeuge für Aufgaben, Notizen, Erinnerungen, Gedächtnis, Rechnen, Uhrzeit und Wetter.\n"
                "- Für aktuelle Informationen aus dem Internet nutze web_research"
                + ("" if settings.get("search_enabled", True) else " (derzeit deaktiviert)")
                + ".\n"
                "- Löschvorgänge und Gedächtniseinträge muss der Nutzer bestätigen; kündige sie an und warte auf die Bestätigung."
            )
        else:
            blocks.append("WERKZEUGE\n- Werkzeuge sind vom Nutzer deaktiviert. Antworte aus eigenem Wissen.")

        return "\n\n".join(blocks)

    def _body(self, model: str, contents: list[dict], settings: dict, declarations: list[dict]) -> dict:
        generation: dict[str, Any] = {"temperature": 0.85, "topP": 0.95, "maxOutputTokens": 2048}
        if model.startswith("gemini-2.5-flash"):
            generation["thinkingConfig"] = {"thinkingBudget": 0}
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": self._system_prompt(settings)}]},
            "contents": contents,
            "generationConfig": generation,
        }
        if declarations:
            body["tools"] = [{"functionDeclarations": declarations}]
        return body

    async def _stream_chunks(self, model: str, body: dict) -> AsyncIterator[dict]:
        url = f"{app_config.GEMINI_ENDPOINT}/models/{model}:streamGenerateContent?alt=sse"
        headers = {"x-goog-api-key": self.cfg.gemini_api_key, "content-type": "application/json"}
        timeout = httpx.Timeout(self.cfg.request_timeout, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code >= 400:
                    raw = await response.aread()
                    raise self._api_error(response.status_code, raw)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        continue

    def _api_error(self, status: int, raw: bytes) -> HopeBrainError:
        detail = ""
        try:
            detail = ((json.loads(raw.decode("utf-8", "replace")).get("error") or {}).get("message")) or ""
        except json.JSONDecodeError:
            detail = raw.decode("utf-8", "replace")
        detail = security.mask_secret(detail[:300], self.cfg.gemini_api_key)
        if status == 400:
            hint = "Gemini hat die Anfrage abgelehnt."
        elif status in (401, 403):
            hint = "Der Gemini-API-Schlüssel wurde abgelehnt. Bitte prüfe GEMINI_API_KEY."
        elif status == 404:
            hint = "Das gewählte Gemini-Modell ist nicht verfügbar."
        elif status == 429:
            hint = "Das Gemini-Kontingent ist gerade erschöpft. Bitte später erneut versuchen."
        elif status >= 500:
            hint = "Der Gemini-Dienst ist momentan nicht erreichbar."
        else:
            hint = "Unerwarteter Fehler des Gemini-Dienstes."
        return HopeBrainError(f"{hint} (HTTP {status}) {detail}".strip())
