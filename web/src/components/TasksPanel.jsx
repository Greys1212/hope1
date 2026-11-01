import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

export default function TasksPanel() {
  const [tasks, setTasks] = useState([]);
  const [reminders, setReminders] = useState([]);
  const [title, setTitle] = useState('');
  const [priority, setPriority] = useState('mittel');
  const [dueAt, setDueAt] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [taskData, reminderData] = await Promise.all([api.tasks('all'), api.reminders()]);
      setTasks(taskData.tasks || []);
      setReminders(reminderData.reminders || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const addTask = async (event) => {
    event.preventDefault();
    if (!title.trim()) return;
    try {
      const data = await api.addTask({
        title: title.trim(),
        priority,
        due_at: dueAt || null,
        notes: '',
      });
      setTasks(data.tasks || []);
      setTitle('');
      setDueAt('');
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const complete = async (id) => {
    try {
      await api.completeTask(id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Aufgabe löschen?')) return;
    try {
      await api.deleteTask(id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const removeReminder = async (id) => {
    if (!window.confirm('Erinnerung löschen?')) return;
    try {
      await api.deleteReminder(id);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="panel">
      <h2 className="panel__title">Aufgaben</h2>
      {error && <p className="panel__hint panel__hint--warn">{error}</p>}

      <form className="inline-form" onSubmit={addTask}>
        <input
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Neue Aufgabe …"
          aria-label="Neue Aufgabe"
        />
        <select value={priority} onChange={(event) => setPriority(event.target.value)} aria-label="Priorität">
          <option value="hoch">Hoch</option>
          <option value="mittel">Mittel</option>
          <option value="niedrig">Niedrig</option>
        </select>
        <input
          type="datetime-local"
          value={dueAt}
          onChange={(event) => setDueAt(event.target.value)}
          aria-label="Fälligkeit"
        />
        <button type="submit" className="solid-btn">
          Hinzufügen
        </button>
      </form>

      <ul className="list">
        {tasks.length === 0 && <li className="list__empty">Noch keine Aufgaben.</li>}
        {tasks.map((task) => (
          <li key={task.id} className={`list__item ${task.done ? 'list__item--done' : ''}`}>
            <button
              type="button"
              className={`check ${task.done ? 'check--on' : ''}`}
              onClick={() => complete(task.id)}
              aria-label={task.done ? 'Erledigt' : 'Als erledigt markieren'}
              disabled={Boolean(task.done)}
            >
              ✓
            </button>
            <div className="list__main">
              <p className="list__title">{task.title}</p>
              <p className="list__meta">
                Priorität {task.priority}
                {task.due_at ? ` · fällig ${task.due_at.replace('T', ' ')}` : ''}
                {task.done ? ' · erledigt' : ''}
              </p>
            </div>
            <button type="button" className="icon-btn icon-btn--danger" onClick={() => remove(task.id)} aria-label="Aufgabe löschen">
              ×
            </button>
          </li>
        ))}
      </ul>

      <h3 className="panel__subtitle">Erinnerungen</h3>
      <ul className="list">
        {reminders.length === 0 && <li className="list__empty">Keine aktiven Erinnerungen.</li>}
        {reminders.map((reminder) => (
          <li key={reminder.id} className="list__item">
            <div className="list__main">
              <p className="list__title">{reminder.text}</p>
              <p className="list__meta">{reminder.remind_at.replace('T', ' ')}</p>
            </div>
            <button
              type="button"
              className="icon-btn icon-btn--danger"
              onClick={() => removeReminder(reminder.id)}
              aria-label="Erinnerung löschen"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
