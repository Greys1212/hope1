import { useEffect, useState } from 'react';
import { api } from '../api';

const STATUS_LABEL = {
  ok: 'ausgeführt',
  bestaetigt: 'bestätigt',
  bestaetigung_noetig: 'wartet auf Freigabe',
  abgelehnt: 'abgelehnt',
  fehler: 'Fehler',
};

export default function LogPanel() {
  const [actions, setActions] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const data = await api.actions();
        setActions(data.actions || []);
      } catch (err) {
        setError(err.message);
      }
    })();
  }, []);

  return (
    <div className="panel">
      <h2 className="panel__title">Aktionsprotokoll</h2>
      <p className="panel__text">
        Jede Werkzeugnutzung, jede Einstellungsänderung und jede Bestätigung wird hier festgehalten – lesbar und
        nachvollziehbar.
      </p>
      {error && <p className="panel__hint panel__hint--warn">{error}</p>}

      <ul className="list">
        {actions.length === 0 && <li className="list__empty">Noch keine Aktionen protokolliert.</li>}
        {actions.map((action) => (
          <li key={action.id} className="list__item">
            <div className="list__main">
              <p className="list__title">
                {action.action}
                {action.sensitive ? ' · sensibel' : ''}
              </p>
              <p className="list__body">{action.detail}</p>
              <p className="list__meta">
                {new Date(action.created_at).toLocaleString('de-DE')} · {STATUS_LABEL[action.status] || action.status}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
