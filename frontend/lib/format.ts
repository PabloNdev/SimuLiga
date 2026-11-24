export function formatProbability(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value >= 0.995) return "99%+";
  if (value < 0.005) return value <= 0 ? "0%" : "<1%";
  if (value < 0.1) return `${(value * 100).toFixed(1)}%`;
  return `${Math.round(value * 100)}%`;
}

export function formatSignedProbability(value: number): string {
  const sign = value > 0 ? "+" : "";
  if (Math.abs(value) < 0.005) return "0%";
  return `${sign}${Math.round(value * 100)}%`;
}

export function formatPoints(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(1);
}

export function formatSignedPoints(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}`;
}

export function formatElo(value: number): string {
  return Math.round(value).toString();
}

export function formatUpdatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function deltaTone(value: number): "up" | "down" | "flat" {
  if (value > 0.005) return "up";
  if (value < -0.005) return "down";
  return "flat";
}
