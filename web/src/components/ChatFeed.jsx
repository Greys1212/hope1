import ConfirmCard from './ConfirmCard';

const SUGGESTIONS = [
  'Plane meinen Tag und priorisiere die wichtigsten Aufgaben.',
  'Wie wird das Wetter in Berlin morgen?',
  'Rechne 18 % von 245.',
  'Notiere: Projekt Atlas – Kickoff am Montag.',
];

function Typing() {
  return (
    <span className="typing" aria-label="HOPE schreibt">
      <i />
      <i />
      <i />
    </span>
  );
}

function Message({ message, onDecide }) {
  if (message.role === 'system') {
    return <div className="msg msg--system">{message.content}</div>;
  }

  const isUser = message.role === 'user';
  return (
    <article className={`msg ${isUser ? 'msg--user' : 'msg--assistant'} ${message.failed ? 'msg--failed' : ''}`}>
      {!isUser && <span className="msg__author">HOPE</span>}

      {message.tools?.length > 0 && (
        <div className="msg__tools">
          {message.tools.map((tool, index) => (
            <span key={`${tool.name}-${index}`} className={`chip ${tool.status === 'laeuft' ? 'chip--live' : ''}`}>
              <span className="chip__dot" aria-hidden="true" />
              {tool.label || tool.name}
            </span>
          ))}
        </div>
      )}

      <div className="msg__body">
        {message.content}
        {message.streaming && message.content && <span className="caret" aria-hidden="true" />}
        {message.streaming && !message.content && <Typing />}
      </div>

      {message.attachments?.length > 0 && (
        <div className="msg__files">
          {message.attachments.map((name) => (
            <span key={name} className="file-chip">
              {name}
            </span>
          ))}
        </div>
      )}

      {message.confirms?.map((confirm) => (
        <ConfirmCard key={confirm.id} confirm={confirm} onDecide={onDecide} />
      ))}
    </article>
  );
}

export default function ChatFeed({ feedRef, messages, onDecide, onSuggestion, geminiReady, onOpenSettings }) {
  return (
    <div className="feed" ref={feedRef}>
      <div className="feed__inner">
        {messages.length === 0 ? (
          <div className="empty">
            <h1 className="empty__title">Willkommen zurück.</h1>
            <p className="empty__text">
              Ich bin HOPE. Ich höre zu, denke mit und behalte im Blick, was wichtig ist.
            </p>

            {!geminiReady && (
              <div className="empty__warn">
                <strong>Hinweis:</strong> Es ist noch kein Gemini-API-Schlüssel hinterlegt – ohne Schlüssel kann ich
                nicht antworten.
                <button type="button" className="link-btn" onClick={onOpenSettings}>
                  Details
                </button>
              </div>
            )}

            <div className="suggestions">
              {SUGGESTIONS.map((text) => (
                <button key={text} type="button" className="suggestion" onClick={() => onSuggestion(text)}>
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => <Message key={message.id} message={message} onDecide={onDecide} />)
        )}
      </div>
    </div>
  );
}
