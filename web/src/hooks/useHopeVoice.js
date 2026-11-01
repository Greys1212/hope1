import { useCallback, useEffect, useRef, useState } from 'react';

const RecognitionCtor =
  typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

/** Entfernt Markdown und Sonderzeichen, damit das Vorlesen natürlich klingt. */
function stripForSpeech(text) {
  return (text || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/^[\s>*#-]+/gm, ' ')
    .replace(/[*_#>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Teilt lange Antworten in Sätze, damit die Ausgabe nicht abbricht. */
function splitForSpeech(text, max = 180) {
  const sentences = text.match(/[^.!?…]+[.!?…]*/g) || [text];
  const chunks = [];
  let current = '';
  for (const sentence of sentences) {
    if (current && (current + sentence).length > max) {
      chunks.push(current.trim());
      current = sentence;
    } else {
      current += sentence;
    }
  }
  if (current.trim()) chunks.push(current.trim());
  return chunks;
}

export function useHopeVoice({ settings, voiceProfile, onFinalTranscript }) {
  const [speaking, setSpeaking] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState('');
  const [voices, setVoices] = useState([]);
  const [error, setError] = useState('');

  const recognitionRef = useRef(null);
  const watchRef = useRef(false);
  const speakingRef = useRef(false);
  const settingsRef = useRef(settings);
  const profileRef = useRef(voiceProfile);
  const transcriptRef = useRef(onFinalTranscript);
  const startRef = useRef(null);

  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);
  useEffect(() => {
    profileRef.current = voiceProfile;
  }, [voiceProfile]);
  useEffect(() => {
    transcriptRef.current = onFinalTranscript;
  }, [onFinalTranscript]);

  useEffect(() => {
    const synth = window.speechSynthesis;
    if (!synth) return undefined;
    const load = () => setVoices(synth.getVoices());
    load();
    synth.addEventListener('voiceschanged', load);
    return () => {
      synth.removeEventListener('voiceschanged', load);
      synth.cancel();
    };
  }, []);

  const pickVoice = useCallback(() => {
    const synth = window.speechSynthesis;
    const list = voices.length ? voices : synth?.getVoices?.() || [];
    const profile = profileRef.current || {};
    const langPrefix = String(profile.language || 'de-DE').slice(0, 2).toLowerCase();
    const sameLang = list.filter((voice) => String(voice.lang || '').toLowerCase().startsWith(langPrefix));
    if (!sameLang.length) return null;

    const wanted = String(settingsRef.current?.voice_name || '').toLowerCase();
    if (wanted) {
      const exact = sameLang.find((voice) => voice.name.toLowerCase() === wanted);
      if (exact) return exact;
    }
    const hints = (profile.prefer || []).map((hint) => hint.toLowerCase());
    return (
      sameLang.find((voice) => hints.some((hint) => voice.name.toLowerCase().includes(hint))) ||
      sameLang.find((voice) => /female|frau|anna|katja|marlene|vicki/i.test(voice.name)) ||
      sameLang[0]
    );
  }, [voices]);

  const stopSpeaking = useCallback(() => {
    window.speechSynthesis?.cancel();
    speakingRef.current = false;
    setSpeaking(false);
  }, []);

  const speak = useCallback(
    (text) => {
      const synth = window.speechSynthesis;
      if (!synth || !settingsRef.current?.tts_enabled) return;
      const clean = stripForSpeech(text);
      if (!clean) return;

      synth.cancel();
      const profile = profileRef.current || {};
      const voice = pickVoice();
      const parts = splitForSpeech(clean);
      let index = 0;

      speakingRef.current = true;
      setSpeaking(true);

      const next = () => {
        if (index >= parts.length) {
          speakingRef.current = false;
          setSpeaking(false);
          return;
        }
        const utterance = new SpeechSynthesisUtterance(parts[index]);
        index += 1;
        utterance.lang = profile.language || 'de-DE';
        utterance.rate = profile.rate ?? 1;
        utterance.pitch = profile.pitch ?? 1.05;
        if (voice) utterance.voice = voice;
        utterance.onend = next;
        utterance.onerror = () => {
          speakingRef.current = false;
          setSpeaking(false);
        };
        synth.speak(utterance);
      };

      next();
    },
    [pickVoice],
  );

  const startListening = useCallback(() => {
    if (!RecognitionCtor) {
      setError('Dieser Browser unterstützt keine Spracherkennung. Nutze Chrome oder Edge.');
      return;
    }
    if (!settingsRef.current?.stt_enabled) {
      setError('Spracherkennung ist in den Einstellungen deaktiviert.');
      return;
    }
    stopSpeaking();
    watchRef.current = true;
    setError('');
    if (recognitionRef.current) return;

    const recognition = new RecognitionCtor();
    recognition.lang = settingsRef.current?.language || 'de-DE';
    recognition.continuous = true;
    recognition.interimResults = true;

    recognition.onresult = (event) => {
      if (speakingRef.current) stopSpeaking();
      let finalText = '';
      let interimText = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) finalText += result[0].transcript;
        else interimText += result[0].transcript;
      }
      setInterim(interimText.trim());
      if (finalText.trim()) {
        setInterim('');
        transcriptRef.current?.(finalText.trim());
      }
    };

    recognition.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        watchRef.current = false;
        setListening(false);
        setError('Mikrofonzugriff verweigert – bitte im Browser erlauben.');
      }
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setListening(false);
      if (watchRef.current && settingsRef.current?.continuous_mode) {
        setTimeout(() => {
          if (watchRef.current) startRef.current?.();
        }, 350);
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setListening(true);
    } catch {
      recognitionRef.current = null;
      setListening(false);
      setError('Mikrofon konnte nicht gestartet werden.');
    }
  }, [stopSpeaking]);

  startRef.current = startListening;

  const stopListening = useCallback(() => {
    watchRef.current = false;
    setInterim('');
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    if (recognition) {
      recognition.onend = null;
      try {
        recognition.stop();
      } catch {
        /* bereits beendet */
      }
    }
    setListening(false);
  }, []);

  useEffect(
    () => () => {
      watchRef.current = false;
      recognitionRef.current?.abort?.();
    },
    [],
  );

  return {
    speaking,
    listening,
    interim,
    voices,
    error,
    setError,
    speak,
    stopSpeaking,
    startListening,
    stopListening,
    ttsSupported: typeof window !== 'undefined' && Boolean(window.speechSynthesis),
    sttSupported: Boolean(RecognitionCtor),
  };
}
