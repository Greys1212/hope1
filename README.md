# HOPE — Hyper Intelligent Personal Assistant

HOPE is a voice-controlled personal AI assistant: **Google Gemini** for intelligence, a **FastAPI**
backend with persistent **SQLite** memory and tools, and a futuristic **React** interface that works
on a desktop PC and on a smartphone.

## Quick start

```bash
docker compose -f docker-compose.base44.yml up -d --build
```

| Service | URL |
| --- | --- |
| Interface | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

SQLite lives in the `hope_data` volume (`/data/hope.db`) and is created on the first API start.

## 1. Configure the Gemini API key

HOPE needs a Google Gemini key from <https://aistudio.google.com/apikey>. It is stored as the
secret **`GEMINI_API_KEY`** and delivered to the container through `/run/base44/app.env` — it is
never written into the repository.

```bash
# locally, without the platform secret store:
export GEMINI_API_KEY="…"
docker compose -f docker-compose.base44.yml up -d
```

Without a key HOPE still starts: the status bar shows **“API-Schlüssel fehlt”**, `/api/health`
reports `"gemini": false`, and the chat answers with a clear explanation instead of a fake reply.

## 2. Project structure

| File | Purpose |
| --- | --- |
| `api/main.py` | Application entry point, REST + SSE endpoints |
| `api/hope_brain.py` | Gemini intelligence: system prompt, streaming, tool loop, research |
| `api/hope_voice.py` | Voice profiles, languages, speed/pitch validation |
| `api/hope_memory.py` | Persistent memory: conversations, facts, tasks, notes, action log |
| `api/hope_tools.py` | Tools and integrations (tasks, notes, reminders, calculator, weather, research) |
| `api/hope_security.py` | Input validation, confirmation policy, secret masking |
| `api/hope_interface.py` | Bootstrap payload for the UI (status, settings, capabilities) |
| `api/config.py` | Configuration from environment variables, HOPE persona |
| `web/src/` | React interface: AI orb, waveform, chat, composer, command center |

## 3. What works — and what does not

**Works**

- Streaming conversations with context, persistent history and per-conversation titles.
- Persistent memory: approved facts are injected into every prompt; new entries require an
  explicit confirmation; everything is editable in the command center.
- Tools: tasks, notes, reminders, memory, safe calculator (no `eval`), clock, weather
  (Open-Meteo, no key needed) and web research through Gemini Google Search grounding.
- Voice in the browser (Web Speech API): text-to-speech, speech-to-text, voice selection, adjustable
  speaking rate and pitch, continuous conversation mode, wake word “HOPE”, interruptible speech,
  live transcript.
- Image / PDF / text attachments are passed to Gemini as inline data (max 3 files, 8 MB each).
- Security: confirmation before deletes and memory writes, argument validation against the tool
  schema, no shell/command tool at all, complete action log, integrations can be switched off.

**Not implemented (and not pretended to be)**

- Native server-side TTS/STT models — speech runs in the browser, no audio leaves the device.
- Opening applications, controlling the PC, sending messages, purchases, file-system search.
- Push notifications for reminders: they are stored and listed, but nothing fires them on a timer.
- Native mobile apps — the interface is responsive and works on a phone browser.

## 4. Install dependencies manually

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r api/requirements.txt
npm install --prefix web
```

## 5. Run without Docker

```bash
uvicorn main:app --app-dir api --reload --port 8000
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev --prefix web
```

## 6. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| “API-Schlüssel fehlt”, answers not generated | `GEMINI_API_KEY` is missing or empty. Set the secret and restart the API. |
| `Der Gemini-API-Schlüssel wurde abgelehnt. (HTTP 403)` | Key invalid, restricted or quota-exhausted. Create a new key in AI Studio. |
| `Das Gemini-Kontingent ist gerade erschöpft.` | Free-tier rate limit reached — wait or use another model in the settings. |
| Mic button does nothing | The browser does not support the Web Speech API (Firefox) or the microphone is blocked; allow it and use Chrome/Edge. |
| No audio | The browser needs a user gesture before speaking, and TTS must be enabled in the settings. |
| `docker compose` fails on `/run/base44/app.env` | The platform secret file is missing; start the stack from the Base44 sandbox or create that file. |
| Interface loads, API calls fail | Check `docker compose logs api` — usually `pip install` still running or the API crashed; the web service waits for a healthy API. |
| Wanted a clean memory | `docker compose -f docker-compose.base44.yml down` then remove the `hope_data` volume. |
