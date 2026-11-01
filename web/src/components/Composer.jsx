import { useEffect, useRef, useState } from 'react';

function IconAttach() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path
        d="M8 7v8a4 4 0 0 0 8 0V6a3 3 0 0 0-6 0v9a1.5 1.5 0 0 0 3 0V7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconMic() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="none" stroke="currentColor" strokeWidth="1.7" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

function IconSend() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d="M4 12 20 5l-7 15-2.2-5.8L4 12Z" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  );
}

function IconStop() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
      <rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />
    </svg>
  );
}

export default function Composer({
  onSend,
  streaming,
  listening,
  speaking,
  onToggleMic,
  onStopSpeaking,
  attachments,
  onAttach,
  onRemoveAttachment,
  sttSupported,
}) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`;
  }, [value]);

  const submit = () => {
    if (streaming) return;
    if (!value.trim() && !attachments.length) return;
    onSend(value);
    setValue('');
  };

  return (
    <div className="composer">
      {attachments.length > 0 && (
        <div className="composer__files">
          {attachments.map((file, index) => (
            <span key={`${file.name}-${index}`} className="file-chip">
              {file.name}
              <button type="button" onClick={() => onRemoveAttachment(index)} aria-label={`${file.name} entfernen`}>
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="composer__box">
        <button
          type="button"
          className="icon-btn"
          onClick={() => fileRef.current?.click()}
          aria-label="Datei anhängen"
          title="Bild, PDF oder Text anhängen"
        >
          <IconAttach />
        </button>
        <input
          ref={fileRef}
          className="visually-hidden"
          type="file"
          multiple
          accept="image/*,application/pdf,text/plain"
          onChange={(event) => {
            onAttach(event.target.files);
            event.target.value = '';
          }}
        />

        <textarea
          ref={textareaRef}
          value={value}
          rows={1}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={listening ? 'Ich höre zu – sprich einfach weiter …' : 'Frag HOPE etwas …'}
          aria-label="Nachricht an HOPE"
        />

        {speaking && (
          <button
            type="button"
            className="icon-btn icon-btn--stop"
            onClick={onStopSpeaking}
            aria-label="Sprachausgabe unterbrechen"
            title="Sprachausgabe unterbrechen"
          >
            <IconStop />
          </button>
        )}

        <button
          type="button"
          className={`icon-btn icon-btn--mic ${listening ? 'is-active' : ''}`}
          onClick={onToggleMic}
          disabled={!sttSupported}
          aria-pressed={listening}
          aria-label={listening ? 'Sprachmodus beenden' : 'Sprachmodus starten'}
          title={sttSupported ? 'Sprachmodus' : 'Spracherkennung wird von diesem Browser nicht unterstützt'}
        >
          <IconMic />
        </button>

        <button
          type="button"
          className="send-btn"
          onClick={submit}
          disabled={streaming || (!value.trim() && !attachments.length)}
          aria-label="Senden"
        >
          <IconSend />
        </button>
      </div>

      <p className="composer__hint">Enter sendet · Shift + Enter für eine neue Zeile</p>
    </div>
  );
}
