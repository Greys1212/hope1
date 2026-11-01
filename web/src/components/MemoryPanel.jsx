import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

const CATEGORIES = ['fakt', 'vorliebe', 'projekt', 'notiz'];

export default function MemoryPanel() {
  const [memories, setMemories] = useState([]);
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('fakt');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const data = await api.memory();
      setMemories(data.memories || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const add = async (event) => {
    event.preventDefault();
    if (!content.trim()) return;
    try {
      const data = await api.addMemory(content.trim(), category);
      setMemories(data.memories || []);
      setContent('');
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Diesen Gedächtniseintrag löschen?')) return;
    try {
      await api.deleteMemory(id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="panel">
      <h2 className="panel__title">Gedächtnis</h2>
      <p className="panel__text">
        Diese Fakten kennt HOPE dauerhaft. Du entscheidest, was gespeichert bleibt – neue Einträge legt HOPE nur nach
        deiner Bestätigung an.
      </p>
      {error && <p className="panel__hint panel__hint--warn">{error}</p>}

      <form className="inline-form" onSubmit={add}>
        <input
          type="text"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          placeholder="Was soll HOPE sich merken?"
          aria-label="Gedächtniseintrag"
        />
        <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Kategorie">
          {CATEGORIES.map((entry) => (
            <option key={entry} value={entry}>
              {entry}
            </option>
          ))}
        </select>
        <button type="submit" className="solid-btn">
          Speichern
        </button>
      </form>

      <ul className="list">
        {memories.length === 0 && <li className="list__empty">Das Gedächtnis ist noch leer.</li>}
        {memories.map((memory) => (
          <li key={memory.id} className="list__item">
            <div className="list__main">
              <p className="list__title">{memory.content}</p>
              <p className="list__meta">
                {memory.category} · {new Date(memory.created_at).toLocaleDateString('de-DE')}
              </p>
            </div>
            <button
              type="button"
              className="icon-btn icon-btn--danger"
              onClick={() => remove(memory.id)}
              aria-label="Gedächtniseintrag löschen"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
