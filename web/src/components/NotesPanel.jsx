import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

export default function NotesPanel() {
  const [notes, setNotes] = useState([]);
  const [query, setQuery] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async (search = '') => {
    try {
      const data = await api.notes(search);
      setNotes(data.notes || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load('');
  }, [load]);

  const addNote = async (event) => {
    event.preventDefault();
    if (!title.trim()) return;
    try {
      const data = await api.addNote({ title: title.trim(), body: body.trim() });
      setNotes(data.notes || []);
      setTitle('');
      setBody('');
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Notiz löschen?')) return;
    try {
      await api.deleteNote(id);
      await load(query);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="panel">
      <h2 className="panel__title">Notizen</h2>
      {error && <p className="panel__hint panel__hint--warn">{error}</p>}

      <form className="stack-form" onSubmit={addNote}>
        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Titel"
          aria-label="Notiztitel"
        />
        <textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Inhalt"
          rows={3}
          aria-label="Notizinhalt"
        />
        <button type="submit" className="solid-btn">
          Notiz speichern
        </button>
      </form>

      <input
        type="search"
        className="search"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          load(event.target.value);
        }}
        placeholder="Notizen durchsuchen …"
        aria-label="Notizen durchsuchen"
      />

      <ul className="list">
        {notes.length === 0 && <li className="list__empty">Keine Notizen gefunden.</li>}
        {notes.map((note) => (
          <li key={note.id} className="list__item list__item--column">
            <div className="list__head">
              <p className="list__title">{note.title}</p>
              <button type="button" className="icon-btn icon-btn--danger" onClick={() => remove(note.id)} aria-label="Notiz löschen">
                ×
              </button>
            </div>
            {note.body && <p className="list__body">{note.body}</p>}
            <p className="list__meta">{new Date(note.updated_at).toLocaleString('de-DE')}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
