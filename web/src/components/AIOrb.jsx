export default function AIOrb({ mode = 'idle' }) {
  return (
    <div className={`orb orb--${mode}`} role="img" aria-label={`HOPE-Kern, Status: ${mode}`}>
      <span className="orb__halo" />
      <span className="orb__ring orb__ring--outer" />
      <span className="orb__ring orb__ring--mid" />
      <span className="orb__ring orb__ring--inner" />
      <span className="orb__core" />
      <span className="orb__scan" />
    </div>
  );
}
