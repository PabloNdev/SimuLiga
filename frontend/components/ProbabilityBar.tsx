import type { CSSProperties } from "react";

type Tone = "accent" | "good" | "europe" | "danger" | "team";

export function ProbabilityBar({
  value,
  tone = "accent",
  color,
  label,
}: {
  value: number;
  tone?: Tone;
  color?: string;
  label?: string;
}) {
  const width = Math.max(0, Math.min(1, value)) * 100;
  const style: CSSProperties | undefined = color
    ? ({ "--bar-color": color } as CSSProperties)
    : undefined;
  return (
    <span
      className="bar"
      style={style}
      role="img"
      aria-label={`${label ?? "Probabilidad"}: ${Math.round(value * 100)}%`}
    >
      <span
        className={`bar-fill ${tone === "team" ? "" : tone}`}
        style={{ width: `${width}%` }}
      />
    </span>
  );
}
