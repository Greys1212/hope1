import { useEffect, useState } from 'react';

function Toggle({ label, detail, checked, onChange }) {
  return (
    <label className="toggle">
      <span className="toggle__copy">
        <span className="toggle__label">{label}</span>
        {detail && <span className="toggle__detail">{detail}</span>}
      </span>
      <input type="checkbox" checked={Boolean(checked)} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle__switch" aria-hidden="true" />
    </label>
  );
}

function Range({ label, value, min, max, step, suffix, onCommit }) {
  const [local, setLocal] = useState(value);
  useEffect(() => setLocal(value), [value]);
  return (
    <label className="range">
      <span className="range__head">
        <span>{label}</span>
        <span className="range__value">
          {Number(local).toFixed(2)}
          {suffix}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={local}
        onChange={(event) => setLocal(event.target.value)}
        onPointerUp={() => onCommit(Number(local))}
        onKeyUp={() => onCommit(Number(local))}
        onBlur={() => onCommit(Number(local))}
      />
    </label>
  );
}

export default function SettingsPanel({ settings, models, voice, voiceProfile, onSettingsChange, status }) {
  const [voices, setVoices] = useState([]);

  useEffect(() => {
    const synth = window.speechSynthesis;
    if (!synth) return undefined;
    const load = () => setVoices(synth.getVoices());
    load();
    synth.addEventListener('voiceschanged', load);
    return () => synth.removeEventListener('voiceschanged', load);
  }, []);

  const languagePrefix = String(settings.language || 'de-DE').slice(0, 2).toLowerCase();
  const relevantVoices = voices.filter((entry) => String(entry.lang || '').toLowerCase().startsWith(languagePrefix));

  return (
    <div className="panel">
      <h2 className="panel__title">Einstellungen</h2>

      <section className="panel__section">
        <h3 className="panel__subtitle">Intelligenz</h3>
        <p className={`panel__hint ${status.gemini ? 'panel__hint--ok' : 'panel__hint--warn'}`}>
          {status.gemini
            ? 'Gemini ist verbunden. HOPE nutzt das gewählte Modell für alle Antworten.'
            : 'Kein Gemini-API-Schlüssel hinterlegt. Setze GEMINI_API_KEY als Secret, damit HOPE antworten kann.'}
        </p>
        <label className="field">
          <span>Modell</span>
          <select value={settings.model} onChange={(event) => onSettingsChange({ model: event.target.value })}>
            {(models || []).map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Dialogsprache</span>
          <select value={settings.language} onChange={(event) => onSettingsChange({ language: event.target.value })}>
            {(voice?.languages || []).map((language) => (
              <option key={language.code} value={language.code}>
                {language.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="panel__section">
        <h3 className="panel__subtitle">Stimme</h3>
        <label className="field">
          <span>Stimmprofil</span>
          <select
            value={settings.voice_profile}
            onChange={(event) => {
              const profile = (voice?.profiles || []).find((entry) => entry.id === event.target.value);
              onSettingsChange({
                voice_profile: event.target.value,
                voice_rate: profile?.rate ?? settings.voice_rate,
                voice_pitch: profile?.pitch ?? settings.voice_pitch,
              });
            }}
          >
            {(voice?.profiles || []).map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.label}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Systemstimme</span>
          <select value={settings.voice_name} onChange={(event) => onSettingsChange({ voice_name: event.target.value })}>
            <option value="">Automatisch (beste weibliche Stimme)</option>
            {relevantVoices.map((entry) => (
              <option key={entry.name} value={entry.name}>
                {entry.name} ({entry.lang})
              </option>
            ))}
          </select>
        </label>

        <Range
          label="Sprechtempo"
          value={settings.voice_rate}
          min={0.6}
          max={1.6}
          step={0.02}
          suffix="×"
          onCommit={(value) => onSettingsChange({ voice_rate: value })}
        />
        <Range
          label="Tonhöhe"
          value={settings.voice_pitch}
          min={0.7}
          max={1.4}
          step={0.02}
          suffix=""
          onCommit={(value) => onSettingsChange({ voice_pitch: value })}
        />

        <Toggle
          label="Sprachausgabe"
          detail="Antworten automatisch vorlesen"
          checked={settings.tts_enabled}
          onChange={(value) => onSettingsChange({ tts_enabled: value })}
        />
        <Toggle
          label="Spracherkennung"
          detail="Mikrofon und Transkription erlauben"
          checked={settings.stt_enabled}
          onChange={(value) => onSettingsChange({ stt_enabled: value })}
        />
        <Toggle
          label="Sprachmodus"
          detail="Nach jeder Antwort automatisch weiter zuhören"
          checked={settings.continuous_mode}
          onChange={(value) => onSettingsChange({ continuous_mode: value })}
        />
        <Toggle
          label="Aktivierungswort"
          detail="Nur reagieren, wenn du „HOPE“ sagst"
          checked={settings.wake_word}
          onChange={(value) => onSettingsChange({ wake_word: value })}
        />
        <p className="panel__meta">
          Aktives Profil: {voiceProfile?.language} · Tempo {voiceProfile?.rate} · Tonhöhe {voiceProfile?.pitch}. Die
          Sprachausgabe läuft lokal im Browser – es werden keine Audiodaten an HOPE gesendet.
        </p>
      </section>

      <section className="panel__section">
        <h3 className="panel__subtitle">Fähigkeiten & Freigaben</h3>
        <Toggle
          label="Werkzeuge"
          detail="Aufgaben, Notizen, Rechnen, Wetter, Uhrzeit"
          checked={settings.tools_enabled}
          onChange={(value) => onSettingsChange({ tools_enabled: value })}
        />
        <Toggle
          label="Internet-Recherche"
          detail="Google-Search-Grounding über Gemini"
          checked={settings.search_enabled}
          onChange={(value) => onSettingsChange({ search_enabled: value })}
        />
        <Toggle
          label="Gedächtnis"
          detail="Freigegebene Fakten in Antworten berücksichtigen"
          checked={settings.memory_enabled}
          onChange={(value) => onSettingsChange({ memory_enabled: value })}
        />
        <p className="panel__meta">
          Löschvorgänge und Gedächtniseinträge erfordern immer eine ausdrückliche Bestätigung. Jede Aktion wird im
          Protokoll festgehalten.
        </p>
      </section>
    </div>
  );
}
