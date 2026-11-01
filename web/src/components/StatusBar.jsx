const PANEL_LABELS = {
  settings: 'Einstellungen',
  tasks: 'Aufgaben',
  notes: 'Notizen',
  memory: 'Gedächtnis',
  log: 'Protokoll',
  system: 'System',
};

export default function StatusBar({ status, mode, onMenu, onOpenPanel }) {
  return (
    <header className="status-bar">
      <div className="status-bar__left">
        <button type="button" className="icon-btn status-bar__menu" onClick={onMenu} aria-label="Verlauf öffnen">
          <span aria-hidden="true">☰</span>
        </button>
        <span className={`pulse pulse--${mode}`} aria-hidden="true" />
        <span className="status-bar__title">HOPE</span>
        <span className="status-bar__sub">{status.model}</span>
      </div>

      <div className="status-bar__right">
        <span className={`pill ${status.gemini ? 'pill--ok' : 'pill--warn'}`}>
          {status.gemini ? 'KI verbunden' : 'API-Schlüssel fehlt'}
        </span>
        <span className="pill pill--muted">{status.tools} Werkzeuge</span>
        <span className="pill pill--muted">{status.memory_entries} im Gedächtnis</span>
        <button type="button" className="ghost-btn" onClick={() => onOpenPanel('settings')}>
          {PANEL_LABELS.settings}
        </button>
        <button type="button" className="ghost-btn ghost-btn--accent" onClick={() => onOpenPanel('tasks')}>
          Aufgaben
        </button>
      </div>
    </header>
  );
}
