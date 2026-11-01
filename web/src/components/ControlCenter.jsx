import { useEffect } from 'react';
import SettingsPanel from './SettingsPanel';
import TasksPanel from './TasksPanel';
import NotesPanel from './NotesPanel';
import MemoryPanel from './MemoryPanel';
import LogPanel from './LogPanel';

const TABS = [
  { id: 'settings', label: 'Einstellungen' },
  { id: 'tasks', label: 'Aufgaben' },
  { id: 'notes', label: 'Notizen' },
  { id: 'memory', label: 'Gedächtnis' },
  { id: 'log', label: 'Protokoll' },
  { id: 'system', label: 'System' },
];

function SystemPanel({ status }) {
  const rows = [
    ['Gemini-API', status.gemini ? 'verbunden' : 'nicht konfiguriert'],
    ['Modell', status.model],
    ['Werkzeuge', `${status.tools} aktiv`],
    ['Recherche', status.research ? 'freigegeben' : 'deaktiviert'],
    ['Gedächtnis', `${status.memory_entries} Einträge`],
    ['Unterhaltungen', `${status.conversations}`],
  ];
  return (
    <div className="panel">
      <h2 className="panel__title">Systemstatus</h2>
      <p className="panel__text">
        HOPE verbindet eine Gemini-Intelligenz mit lokalem Gedächtnis, Werkzeugen und Sprache. Alle Zugangsdaten
        liegen ausschließlich in Umgebungsvariablen.
      </p>
      <div className="stat-list">
        {rows.map(([label, value]) => (
          <div key={label} className="stat-row">
            <span>{label}</span>
            <span className={value === 'nicht konfiguriert' || value === 'deaktiviert' ? 'stat-row__warn' : 'stat-row__ok'}>
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ControlCenter({
  panel,
  onPanelChange,
  onClose,
  settings,
  models,
  voice,
  voiceProfile,
  onSettingsChange,
  status,
}) {
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div className="cc-backdrop" onClick={onClose}>
      <div
        className="cc"
        role="dialog"
        aria-modal="true"
        aria-label="Kommandozentrale"
        onClick={(event) => event.stopPropagation()}
      >
        <nav className="cc__nav">
          <p className="cc__brand">Kommandozentrale</p>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`cc__tab ${panel === tab.id ? 'cc__tab--active' : ''}`}
              onClick={() => onPanelChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
          <button type="button" className="cc__close" onClick={onClose} aria-label="Schließen">
            ×
          </button>
        </nav>

        <div className="cc__body">
          {panel === 'settings' && (
            <SettingsPanel
              settings={settings}
              models={models}
              voice={voice}
              voiceProfile={voiceProfile}
              onSettingsChange={onSettingsChange}
              status={status}
            />
          )}
          {panel === 'tasks' && <TasksPanel />}
          {panel === 'notes' && <NotesPanel />}
          {panel === 'memory' && <MemoryPanel />}
          {panel === 'log' && <LogPanel />}
          {panel === 'system' && <SystemPanel status={status} />}
        </div>
      </div>
    </div>
  );
}
