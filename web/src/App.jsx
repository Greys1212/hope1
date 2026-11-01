import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, streamChat } from './api';
import { useHopeVoice } from './hooks/useHopeVoice';
import Sidebar from './components/Sidebar';
import StatusBar from './components/StatusBar';
import AIOrb from './components/AIOrb';
import Waveform from './components/Waveform';
import ChatFeed from './components/ChatFeed';
import Composer from './components/Composer';
import ControlCenter from './components/ControlCenter';

const toUiMessage = (message) => ({
  id: message.id,
  role: message.role,
  content: message.content,
  tools: [],
  confirms: [],
});

const MODE_HINT = {
  idle: 'Bereit',
  listening: 'Ich höre zu …',
  thinking: 'Ich verarbeite …',
  speaking: 'Ich spreche …',
};

export default function App() {
  const [boot, setBoot] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState('');
  const [panel, setPanel] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [voiceLoop, setVoiceLoop] = useState(false);

  const feedRef = useRef(null);
  const answerRef = useRef('');
  const sendRef = useRef(() => {});
  const stopListeningRef = useRef(() => {});

  const settings = boot?.settings || {};
  const speechRate = Number(settings.voice_rate ?? 1);
  const speechPitch = Number(settings.voice_pitch ?? 1.05);
  const speechLanguage = settings.language || 'de-DE';

  const handleTranscript = useCallback(
    (text) => {
      let spoken = text;
      if (settings.wake_word) {
        const match = /\bhope\b/i.exec(text);
        if (!match) return;
        spoken = text.slice(match.index + match[0].length).replace(/^[\s,.:;-]+/, '');
        if (!spoken) return;
      }
      stopListeningRef.current();
      sendRef.current(spoken);
    },
    [settings.wake_word],
  );

  const voiceProfile = useMemo(
    () => ({
      language: speechLanguage,
      rate: speechRate,
      pitch: speechPitch,
      prefer: ['Google', 'Microsoft', 'Anna', 'Katja', 'female'],
      voice_name: settings.voice_name || '',
    }),
    [speechLanguage, speechRate, speechPitch, settings.voice_name],
  );

  const voice = useHopeVoice({ settings, voiceProfile, onFinalTranscript: handleTranscript });
  stopListeningRef.current = voice.stopListening;

  const refreshConversations = useCallback(async () => {
    try {
      const data = await api.conversations();
      setConversations(data.conversations || []);
    } catch {
      /* Die Liste ist nicht kritisch */
    }
  }, []);

  const loadConversation = useCallback(async (id) => {
    try {
      const thread = await api.messages(id);
      setConversationId(id);
      setMessages((thread.messages || []).map(toUiMessage));
      setError('');
      setSidebarOpen(false);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.bootstrap();
        if (cancelled) return;
        setBoot(data);
        setConversations(data.conversations || []);
        if (data.conversations?.length) {
          const thread = await api.messages(data.conversations[0].id);
          if (cancelled) return;
          setConversationId(data.conversations[0].id);
          setMessages((thread.messages || []).map(toUiMessage));
        }
      } catch (err) {
        if (!cancelled) setError(`Verbindung zu HOPE fehlgeschlagen: ${err.message}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const element = feedRef.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [messages]);

  const send = useCallback(
    async (rawText) => {
      const text = String(rawText ?? '').trim();
      const files = attachments;
      if ((!text && !files.length) || streaming) return;

      setError('');
      setAttachments([]);
      setStreaming(true);
      answerRef.current = '';

      const liveId = `live-${Date.now()}`;
      setMessages((previous) => [
        ...previous,
        {
          id: `user-${Date.now()}`,
          role: 'user',
          content: text || 'Anhang',
          attachments: files.map((file) => file.name),
        },
        { id: liveId, role: 'assistant', content: '', tools: [], confirms: [], streaming: true },
      ]);

      await streamChat(
        { conversation_id: conversationId, text, attachments: files },
        {
          onStart: (event) => {
            if (!conversationId) setConversationId(event.conversation_id);
          },
          onDelta: (delta) => {
            answerRef.current += delta;
            setMessages((previous) =>
              previous.map((message) =>
                message.id === liveId ? { ...message, content: message.content + delta } : message,
              ),
            );
          },
          onTool: (event) => {
            setMessages((previous) =>
              previous.map((message) => {
                if (message.id !== liveId) return message;
                const tools = [...(message.tools || [])];
                const index = tools.findIndex((tool) => tool.name === event.name && tool.status === 'laeuft');
                if (event.status === 'laeuft') {
                  tools.push({ name: event.name, label: event.label, state: 'laeuft', status: 'laeuft' });
                } else if (index >= 0) {
                  tools[index] = { ...tools[index], label: event.label, state: event.state, status: 'fertig' };
                } else {
                  tools.push({ name: event.name, label: event.label, state: event.state, status: 'fertig' });
                }
                return { ...message, tools };
              }),
            );
          },
          onConfirm: (event) => {
            setMessages((previous) =>
              previous.map((message) =>
                message.id === liveId
                  ? { ...message, confirms: [...(message.confirms || []), { ...event, status: 'offen' }] }
                  : message,
              ),
            );
          },
          onError: (message) => {
            setError(message);
            setMessages((previous) =>
              previous.map((item) => (item.id === liveId ? { ...item, failed: true } : item)),
            );
          },
          onDone: () => {
            setStreaming(false);
            const answer = answerRef.current.trim();
            setMessages((previous) =>
              previous.map((message) => (message.id === liveId ? { ...message, streaming: false } : message)),
            );
            refreshConversations();
            if (answer) voice.speak(answer);
          },
        },
      );
    },
    [attachments, conversationId, refreshConversations, streaming, voice.speak],
  );
  sendRef.current = send;

  // Sprachmodus: nach der Antwort wieder zuhören
  useEffect(() => {
    if (!voiceLoop || !settings.continuous_mode) return;
    if (voice.speaking || streaming || voice.listening) return;
    voice.startListening();
  }, [voiceLoop, settings.continuous_mode, voice.speaking, streaming, voice.listening, voice]);

  // Während HOPE spricht nicht mithören (verhindert Rückkopplung)
  useEffect(() => {
    if (voice.speaking && voice.listening) voice.stopListening();
  }, [voice.speaking, voice.listening, voice]);

  const decide = useCallback(async (confirm, approve) => {
    try {
      const result = await api.decide(confirm.id, approve);
      setMessages((previous) => [
        ...previous.map((message) => ({
          ...message,
          confirms: (message.confirms || []).map((item) =>
            item.id === confirm.id ? { ...item, status: result.status } : item,
          ),
        })),
        { id: `sys-${Date.now()}`, role: 'system', content: result.message },
      ]);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  const updateSettings = useCallback(
    async (patch) => {
      setBoot((previous) =>
        previous ? { ...previous, settings: { ...previous.settings, ...patch } } : previous,
      );
      try {
        const data = await api.updateSettings(patch);
        setBoot((previous) =>
          previous ? { ...previous, settings: data.settings, voice_profile: data.voice_profile } : previous,
        );
        if (patch.tts_enabled === false) voice.stopSpeaking();
        if (patch.stt_enabled === false) setVoiceLoop(false);
      } catch (err) {
        setError(err.message);
      }
    },
    [voice],
  );

  const newConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setError('');
    setSidebarOpen(false);
    voice.stopSpeaking();
  }, [voice]);

  const deleteConversation = useCallback(
    async (id) => {
      if (!window.confirm('Diese Unterhaltung wirklich löschen?')) return;
      try {
        await api.deleteConversation(id);
        if (id === conversationId) newConversation();
        refreshConversations();
      } catch (err) {
        setError(err.message);
      }
    },
    [conversationId, newConversation, refreshConversations],
  );

  const addFiles = useCallback(async (fileList) => {
    const files = Array.from(fileList || []).slice(0, 3);
    const loaded = [];
    for (const file of files) {
      if (file.size > 8 * 1024 * 1024) {
        setError(`${file.name} ist größer als 8 MB.`);
        continue;
      }
      const data = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      loaded.push({ name: file.name, mime_type: file.type || 'application/octet-stream', data });
    }
    if (loaded.length) setAttachments((previous) => [...previous, ...loaded].slice(0, 3));
  }, []);

  const toggleVoiceLoop = useCallback(() => {
    setVoiceLoop((active) => {
      if (active) {
        voice.stopListening();
        return false;
      }
      voice.startListening();
      return true;
    });
  }, [voice]);

  if (!boot) {
    return (
      <div className="boot">
        <div className="ambient" aria-hidden="true" />
        <AIOrb mode={error ? 'idle' : 'thinking'} />
        <h1 className="boot__title">HOPE</h1>
        <p className="boot__hint">{error || 'Systeme werden initialisiert …'}</p>
      </div>
    );
  }

  const mode = streaming
    ? 'thinking'
    : voice.speaking
      ? 'speaking'
      : voice.listening
        ? 'listening'
        : 'idle';

  return (
    <div className="app-shell">
      <div className="ambient" aria-hidden="true" />

      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        activeId={conversationId}
        onSelect={loadConversation}
        onNew={newConversation}
        onDelete={deleteConversation}
        app={boot.app}
        status={boot.status}
      />

      <main className="stage">
        <StatusBar
          status={boot.status}
          mode={mode}
          onMenu={() => setSidebarOpen(true)}
          onOpenPanel={setPanel}
        />

        <section className="orb-stage">
          <AIOrb mode={mode} />
          <Waveform mode={mode} />
          <p className={`orb-stage__hint orb-stage__hint--${mode}`}>
            {MODE_HINT[mode]}
            {voiceLoop && settings.continuous_mode ? ' · Sprachmodus aktiv' : ''}
          </p>
          {voice.interim && <p className="orb-stage__interim">„{voice.interim}“</p>}
          {voice.error && <p className="orb-stage__warn">{voice.error}</p>}
        </section>

        {error && (
          <div className="banner" role="alert">
            <span>{error}</span>
            <button type="button" className="banner__close" onClick={() => setError('')} aria-label="Hinweis schließen">
              ×
            </button>
          </div>
        )}

        <ChatFeed
          feedRef={feedRef}
          messages={messages}
          onDecide={decide}
          onSuggestion={send}
          geminiReady={boot.status.gemini}
          onOpenSettings={() => setPanel('settings')}
        />

        <Composer
          onSend={send}
          streaming={streaming}
          listening={voice.listening}
          speaking={voice.speaking}
          interim={voice.interim}
          onToggleMic={toggleVoiceLoop}
          onStopSpeaking={voice.stopSpeaking}
          attachments={attachments}
          onAttach={addFiles}
          onRemoveAttachment={(index) =>
            setAttachments((previous) => previous.filter((_, position) => position !== index))
          }
          sttSupported={voice.sttSupported}
        />
      </main>

      {panel && (
        <ControlCenter
          panel={panel}
          onPanelChange={setPanel}
          onClose={() => setPanel(null)}
          settings={settings}
          models={boot.models}
          voice={boot.voice}
          voiceProfile={voiceProfile}
          onSettingsChange={updateSettings}
          status={boot.status}
        />
      )}
    </div>
  );
}
