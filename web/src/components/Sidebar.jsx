import AIOrb from './AIOrb';

function formatWhen(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return `${date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })} · ${date.toLocaleTimeString(
    'de-DE',
    { hour: '2-digit', minute: '2-digit' },
  )}`;
}

export default function Sidebar({
  open,
  onClose,
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  app,
  status,
}) {
  return (
    <>
      {open && <button type="button" className="sidebar__backdrop" onClick={onClose} aria-label="Menü schließen" />}
      <aside className={`sidebar ${open ? 'sidebar--open' : ''}`}>
        <div className="sidebar__brand">
          <div className="sidebar__orb">
            <AIOrb mode="idle" />
          </div>
          <div className="sidebar__ident">
            <p className="sidebar__name">{app?.name || 'HOPE'}</p>
            <p className="sidebar__sub">Personal Assistant</p>
          </div>
          <button type="button" className="icon-btn sidebar__close" onClick={onClose} aria-label="Menü schließen">
            ×
          </button>
        </div>

        <button type="button" className="new-chat" onClick={onNew}>
          <span aria-hidden="true">+</span> Neue Unterhaltung
        </button>

        <p className="sidebar__label">Verlauf</p>
        <div className="sidebar__list">
          {conversations.length === 0 && <p className="sidebar__empty">Noch keine Unterhaltung.</p>}
          {conversations.map((conversation) => (
            <div key={conversation.id} className={`thread ${conversation.id === activeId ? 'thread--active' : ''}`}>
              <button type="button" className="thread__open" onClick={() => onSelect(conversation.id)}>
                <span className="thread__title">{conversation.title}</span>
                <span className="thread__meta">
                  {formatWhen(conversation.updated_at)} · {conversation.message_count} Nachrichten
                </span>
              </button>
              <button
                type="button"
                className="thread__delete"
                onClick={() => onDelete(conversation.id)}
                aria-label={`Unterhaltung ${conversation.title} löschen`}
              >
                ×
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar__foot">
          <span className={`dot ${status?.gemini ? 'dot--on' : 'dot--off'}`} />
          <span>{status?.gemini ? `Gemini aktiv · ${status.model}` : 'Gemini nicht verbunden'}</span>
        </div>
      </aside>
    </>
  );
}
