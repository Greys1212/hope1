const BASE = '/api';

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch {
      /* Antwort ohne JSON */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  bootstrap: () => request('/bootstrap'),
  status: () => request('/status'),
  conversations: () => request('/conversations'),
  createConversation: () => request('/conversations', { method: 'POST' }),
  messages: (id) => request(`/conversations/${id}/messages`),
  deleteConversation: (id) => request(`/conversations/${id}`, { method: 'DELETE' }),

  settings: () => request('/settings'),
  updateSettings: (patch) => request('/settings', { method: 'PUT', body: JSON.stringify(patch) }),

  memory: () => request('/memory'),
  addMemory: (content, category) => request('/memory', { method: 'POST', body: JSON.stringify({ content, category }) }),
  deleteMemory: (id) => request(`/memory/${id}`, { method: 'DELETE' }),

  tasks: (status = 'open') => request(`/tasks?status=${status}`),
  addTask: (task) => request('/tasks', { method: 'POST', body: JSON.stringify(task) }),
  completeTask: (id) => request(`/tasks/${id}/complete`, { method: 'POST' }),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),

  notes: (query = '') => request(`/notes?query=${encodeURIComponent(query)}`),
  addNote: (note) => request('/notes', { method: 'POST', body: JSON.stringify(note) }),
  deleteNote: (id) => request(`/notes/${id}`, { method: 'DELETE' }),

  reminders: () => request('/reminders'),
  deleteReminder: (id) => request(`/reminders/${id}`, { method: 'DELETE' }),

  actions: () => request('/actions'),
  decide: (id, approve) => request(`/actions/${id}/decision`, { method: 'POST', body: JSON.stringify({ approve }) }),
};

/**
 * Startet einen Chat-Stream (Server-Sent Events) und ruft die Handler auf.
 * Rückgabe: true, wenn der Stream regulär beendet wurde.
 */
export async function streamChat(payload, handlers = {}) {
  const response = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch {
      /* Antwort ohne JSON */
    }
    handlers.onError?.(detail);
    handlers.onDone?.();
    return false;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finished = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let separator = buffer.indexOf('\n\n');
    while (separator !== -1) {
      const raw = buffer.slice(0, separator).trim();
      buffer = buffer.slice(separator + 2);
      separator = buffer.indexOf('\n\n');
      if (!raw.startsWith('data:')) continue;
      let event;
      try {
        event = JSON.parse(raw.slice(5).trim());
      } catch {
        continue;
      }
      if (event.type === 'start') handlers.onStart?.(event);
      else if (event.type === 'delta') handlers.onDelta?.(event.text);
      else if (event.type === 'tool') handlers.onTool?.(event);
      else if (event.type === 'confirm') handlers.onConfirm?.(event);
      else if (event.type === 'error') handlers.onError?.(event.message);
      else if (event.type === 'done') {
        finished = true;
        handlers.onDone?.(event);
      }
    }
  }
  if (!finished) handlers.onDone?.();
  return finished;
}
