# AGENTS.md – Hinweise für Entwicklung in diesem Repository

## Was das ist
HOPE ist ein zweiteiliges Projekt: eine FastAPI-Anwendung (`api/`) mit Gemini-Intelligenz,
SQLite-Gedächtnis und Werkzeugen sowie eine React/Vite-Oberfläche (`web/`).

## Starten (Sandbox)
```bash
docker compose -f docker-compose.base44.yml up -d --build
curl -s http://localhost:3000/ | head        # Oberfläche
curl -s http://localhost:8000/api/health     # API
```

- `web` läuft auf Host-Port **3000** (Vite-Dev-Server, Live-Reload, Proxy `/api` → `api:8000`).
- `api` läuft auf Host-Port **8000**, automatischer Reload über `uvicorn --reload`.
- SQLite liegt im Volume `hope_data` (`/data/hope.db`); Tabellen werden beim API-Start angelegt.
  Ein Löschen des Volumes setzt Gedächtnis, Aufgaben und Notizen zurück.

## Nicht offensichtlich
- `GEMINI_API_KEY` kommt aus `/run/base44/app.env` (Plattform-Secrets). Fehlt er, bootet die App
  trotzdem; `/api/health` meldet dann `gemini: false` und der Chat liefert eine klare Fehlermeldung.
  Der Schlüssel darf **nie** unter `environment:` in Compose stehen – das würde Dashboard-Werte
  dauerhaft überschreiben.
- Sprachausgabe/-erkennung laufen im Browser (Web Speech API). In Chrome/Edge funktioniert es ohne
  Zusatzpakete; Mikrofonzugriff muss im Browser erlaubt sein.
- Sensible Werkzeuge (`delete_*`, `save_memory`) erzeugen einen Eintrag in `pending_actions`.
  Erst `POST /api/actions/{id}/decision` führt sie aus.
- `BASE44_PREVIEW_MODE=1` erweitert in `web/vite.config.js` nur dann `allowedHosts` um die
  Sandbox-Domain und aktiviert Watch-Polling. Ohne die Variable bleibt das Verhalten unverändert.

## Prüfen
```bash
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/bootstrap | python3 -m json.tool | head -40
docker compose -f docker-compose.base44.yml logs --tail=40 api
```

Es gibt (noch) keine automatisierten Tests. Änderungen an Werkzeugen lassen sich über den Chat
oder direkt über die REST-Endpunkte prüfen.
