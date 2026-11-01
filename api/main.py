"""HOPE – Application Entry Point.

Startet die FastAPI-Anwendung, verbindet Brain, Gedächtnis, Werkzeuge und
Sprachprofil und stellt die REST-/Streaming-Endpunkte für die Oberfläche bereit.
"""
from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import config as app_config
import hope_interface
import hope_memory
import hope_security as security
import hope_tools
import hope_voice
from hope_brain import HopeBrain, NO_KEY_MESSAGE
from hope_memory import HopeMemory

cfg = app_config.config
memory = HopeMemory(cfg.db_path)
memory.init_db()

tools = hope_tools.ToolRegistry(memory)
brain = HopeBrain(cfg, memory, tools)
tools.set_research(brain.research)

app = FastAPI(title="HOPE API", version="1.0", description="Backend des HOPE Personal Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.allowed_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_ATTACHMENT = re.compile(r"^(image/(png|jpe?g|webp|gif)|application/pdf|text/plain)$")


# --------------------------------------------------------------------- Modelle
class Attachment(BaseModel):
    name: str = ""
    mime_type: str = "application/octet-stream"
    data: str = ""


class ChatIn(BaseModel):
    conversation_id: int | None = None
    text: str = ""
    attachments: list[Attachment] = Field(default_factory=list)


class TaskIn(BaseModel):
    title: str
    notes: str = ""
    due_at: str | None = None
    priority: str = "mittel"


class NoteIn(BaseModel):
    title: str
    body: str = ""


class MemoryIn(BaseModel):
    content: str
    category: str = "notiz"


class DecisionIn(BaseModel):
    approve: bool


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# --------------------------------------------------------------------- System
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "gemini": cfg.gemini_ready, "model": cfg.model, "tools": len(tools.tools)}


@app.get("/api/bootstrap")
def bootstrap() -> dict:
    return hope_interface.bootstrap(cfg, memory, tools)


@app.get("/api/status")
def status() -> dict:
    return hope_interface.status(cfg, memory, tools)


@app.get("/api/settings")
def get_settings() -> dict:
    settings = memory.get_settings()
    return {
        "settings": settings,
        "voice_profile": hope_voice.resolve_voice(settings),
        "models": app_config.AVAILABLE_MODELS,
        "languages": hope_voice.LANGUAGES,
        "profiles": list(hope_voice.VOICE_PROFILES.values()),
    }


@app.put("/api/settings")
def update_settings(patch: dict[str, Any]) -> dict:
    clean = hope_interface.sanitize_settings(patch)
    settings = memory.update_settings(clean)
    memory.log_action("update_settings", json.dumps(clean, ensure_ascii=False))
    return {"settings": settings, "voice_profile": hope_voice.resolve_voice(settings)}


# ---------------------------------------------------------------- Gespräche
@app.get("/api/conversations")
def list_conversations() -> dict:
    return {"conversations": memory.list_conversations()}


@app.post("/api/conversations")
def create_conversation() -> dict:
    return {"id": memory.create_conversation()}


@app.get("/api/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int) -> dict:
    conversation = memory.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Unterhaltung nicht gefunden.")
    return {"conversation": conversation, "messages": memory.list_messages(conversation_id)}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int) -> dict:
    memory.delete_conversation(conversation_id)
    memory.log_action("delete_conversation", str(conversation_id), status="bestaetigt", sensitive=True)
    return {"deleted": True}


# --------------------------------------------------------------------- Chat
@app.post("/api/chat")
async def chat(payload: ChatIn) -> StreamingResponse:
    text = security.clean_text(payload.text, security.MAX_USER_TEXT)
    attachments: list[dict] = []
    for attachment in payload.attachments[:4]:
        if not attachment.data:
            continue
        if len(attachment.data) * 3 // 4 > cfg.max_attachment_bytes:
            raise HTTPException(status_code=413, detail="Anhang ist zu groß (max. 8 MB).")
        if not ALLOWED_ATTACHMENT.match(attachment.mime_type):
            raise HTTPException(status_code=415, detail="Nur Bilder, PDF- und Textdateien werden unterstützt.")
        attachments.append(
            {
                "name": security.clean_text(attachment.name, 120),
                "mime_type": attachment.mime_type,
                "data": attachment.data,
            }
        )

    if not text and not attachments:
        raise HTTPException(status_code=400, detail="Die Nachricht ist leer.")

    conversation_id = payload.conversation_id
    if conversation_id is None:
        conversation_id = memory.create_conversation()
    elif memory.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="Unterhaltung nicht gefunden.")

    memory.add_message(conversation_id, "user", text or "Anhang")
    if memory.count_messages(conversation_id) <= 1:
        memory.rename_conversation(conversation_id, (text or "Anhang")[:60])

    settings = memory.get_settings()

    async def event_stream() -> AsyncIterator[str]:
        collected: list[str] = []
        error_message = ""
        yield _sse({"type": "start", "conversation_id": conversation_id})
        try:
            async for event in brain.stream_reply(conversation_id, settings, attachments):
                if event["type"] == "delta":
                    collected.append(event["text"])
                elif event["type"] == "error":
                    error_message = event.get("message", "")
                yield _sse(event)
        except Exception as exc:  # pragma: no cover - Schutznetz für die Oberfläche
            error_message = security.mask_secret(str(exc), cfg.gemini_api_key) or "Unerwarteter Fehler."
            yield _sse({"type": "error", "message": error_message})
        finally:
            answer = "".join(collected).strip()
            if answer:
                memory.add_message(conversation_id, "assistant", answer)
            elif error_message:
                memory.add_message(conversation_id, "assistant", error_message)
        yield _sse({"type": "done", "conversation_id": conversation_id})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ----------------------------------------------------------------- Gedächtnis
@app.get("/api/memory")
def list_memory() -> dict:
    return {"memories": memory.list_memories()}


@app.post("/api/memory")
def add_memory(payload: MemoryIn) -> dict:
    content = security.clean_text(payload.content, 500)
    if not content:
        raise HTTPException(status_code=400, detail="Inhalt fehlt.")
    category = payload.category if payload.category in {"fakt", "vorliebe", "projekt", "notiz"} else "notiz"
    memory_id = memory.add_memory(content, category)
    memory.log_action("add_memory", content, sensitive=True)
    return {"id": memory_id, "memories": memory.list_memories()}


@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: int) -> dict:
    if not memory.delete_memory(memory_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    memory.log_action("delete_memory", str(memory_id), status="bestaetigt", sensitive=True)
    return {"memories": memory.list_memories()}


# ------------------------------------------------------------------ Aufgaben
@app.get("/api/tasks")
def list_tasks(status: str = Query("open")) -> dict:
    return {"tasks": memory.list_tasks(status=status)}


@app.post("/api/tasks")
def add_task(payload: TaskIn) -> dict:
    title = security.clean_text(payload.title, 200)
    if not title:
        raise HTTPException(status_code=400, detail="Titel fehlt.")
    priority = payload.priority if payload.priority in {"niedrig", "mittel", "hoch"} else "mittel"
    memory.add_task(title, security.clean_text(payload.notes, 2000), payload.due_at, priority)
    memory.log_action("add_task", title)
    return {"tasks": memory.list_tasks(status="open")}


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: int) -> dict:
    if not memory.complete_task(task_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    memory.log_action("complete_task", str(task_id))
    return {"tasks": memory.list_tasks(status="open")}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int) -> dict:
    if not memory.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden.")
    memory.log_action("delete_task", str(task_id), status="bestaetigt", sensitive=True)
    return {"tasks": memory.list_tasks(status="open")}


# ------------------------------------------------------------------- Notizen
@app.get("/api/notes")
def list_notes(query: str = Query("")) -> dict:
    return {"notes": memory.list_notes(query)}


@app.post("/api/notes")
def add_note(payload: NoteIn) -> dict:
    title = security.clean_text(payload.title, 200)
    if not title:
        raise HTTPException(status_code=400, detail="Titel fehlt.")
    memory.add_note(title, security.clean_text(payload.body, 8000))
    memory.log_action("add_note", title)
    return {"notes": memory.list_notes()}


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int) -> dict:
    if not memory.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Notiz nicht gefunden.")
    memory.log_action("delete_note", str(note_id), status="bestaetigt", sensitive=True)
    return {"notes": memory.list_notes()}


# -------------------------------------------------------------- Erinnerungen
@app.get("/api/reminders")
def list_reminders() -> dict:
    return {"reminders": memory.list_reminders()}


@app.delete("/api/reminders/{reminder_id}")
def delete_reminder(reminder_id: int) -> dict:
    if not memory.delete_reminder(reminder_id):
        raise HTTPException(status_code=404, detail="Erinnerung nicht gefunden.")
    memory.log_action("delete_reminder", str(reminder_id), status="bestaetigt", sensitive=True)
    return {"reminders": memory.list_reminders()}


# ------------------------------------------------ Protokoll und Bestätigungen
@app.get("/api/actions")
def list_actions() -> dict:
    return {"actions": memory.list_actions()}


@app.post("/api/actions/{pending_id}/decision")
async def decide_action(pending_id: str, payload: DecisionIn) -> dict:
    action = memory.get_pending(pending_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Aktion nicht gefunden.")
    if action["status"] != "offen":
        raise HTTPException(status_code=409, detail="Diese Aktion wurde bereits entschieden.")

    if not payload.approve:
        memory.set_pending_status(pending_id, "abgelehnt")
        memory.log_action(action["tool"], action["summary"], status="abgelehnt", sensitive=True)
        message = f"Abgelehnt: {action['summary']}."
        if action.get("conversation_id"):
            memory.add_message(action["conversation_id"], "system", f"⛔ {message}")
        return {"status": "abgelehnt", "message": message}

    try:
        result = await tools.run_confirmed(action)
    except Exception as exc:
        memory.set_pending_status(pending_id, "fehler")
        memory.log_action(action["tool"], action["summary"], status="fehler", sensitive=True)
        raise HTTPException(status_code=500, detail=f"Aktion fehlgeschlagen: {exc}") from exc

    memory.set_pending_status(pending_id, "bestaetigt")
    message = f"{action['summary']} – {result}"
    if action.get("conversation_id"):
        memory.add_message(action["conversation_id"], "system", f"✅ {message}")
    return {"status": "bestaetigt", "message": message, "result": result}
