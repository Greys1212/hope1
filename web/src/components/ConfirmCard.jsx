export default function ConfirmCard({ confirm, onDecide }) {
  const open = confirm.status === 'offen';
  return (
    <div className={`confirm confirm--${confirm.status}`}>
      <span className="confirm__icon" aria-hidden="true">
        ⚠
      </span>
      <div className="confirm__text">
        <p className="confirm__title">Bestätigung erforderlich</p>
        <p className="confirm__summary">{confirm.summary}</p>
      </div>
      {open ? (
        <div className="confirm__actions">
          <button type="button" className="ghost-btn" onClick={() => onDecide(confirm, false)}>
            Ablehnen
          </button>
          <button type="button" className="solid-btn" onClick={() => onDecide(confirm, true)}>
            Bestätigen
          </button>
        </div>
      ) : (
        <span className={`confirm__status confirm__status--${confirm.status}`}>
          {confirm.status === 'bestaetigt' ? 'Bestätigt' : 'Abgelehnt'}
        </span>
      )}
    </div>
  );
}
