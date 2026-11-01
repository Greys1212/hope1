const BAR_COUNT = 44;

const HEIGHTS = Array.from({ length: BAR_COUNT }, (_, index) => {
  const wave = Math.sin(index * 0.62) + Math.sin(index * 0.21) * 0.6;
  return 26 + Math.round(((wave + 1.6) / 3.2) * 52);
});

export default function Waveform({ mode = 'idle' }) {
  return (
    <div className={`wave wave--${mode}`} aria-hidden="true">
      {HEIGHTS.map((height, index) => (
        <span
          key={index}
          className="wave__bar"
          style={{ '--h': `${height}%`, animationDelay: `${(index % 11) * 70}ms` }}
        />
      ))}
    </div>
  );
}
