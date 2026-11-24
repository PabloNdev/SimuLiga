export function RangeBar({
  p10,
  median,
  p90,
  max = 120,
}: {
  p10: number;
  median: number;
  p90: number;
  max?: number;
}) {
  const scale = (value: number) => Math.max(0, Math.min(100, (value / max) * 100));
  const left = scale(p10);
  const right = scale(p90);
  const mid = scale(median);
  return (
    <div
      className="range"
      title={`Rango probable: ${p10}–${p90} puntos · mediana ${median}`}
      aria-label={`Rango probable de ${p10} a ${p90} puntos, mediana ${median}`}
    >
      <span className="range-track" aria-hidden="true">
        <span
          className="range-span"
          style={{ left: `${left}%`, width: `${Math.max(2, right - left)}%` }}
        />
        <span className="range-mid" style={{ left: `${mid}%` }} />
      </span>
    </div>
  );
}
