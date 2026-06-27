/** Shared INR currency and date formatting helpers. */

export function formatInr(value: string | number): string {
  const num = typeof value === "string" ? Number(value) : value;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(num);
}

export function formatInrAbs(value: string | number): string {
  const num = typeof value === "string" ? Number(value) : value;
  return formatInr(Math.abs(num));
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

export function formatPeriodLabel(
  start: string | null,
  end: string | null,
  fallback?: string,
): string {
  if (!start && !end) return fallback ?? "Unknown period";
  const fmt = (value: string) =>
    new Date(value).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  if (start && end) return `${fmt(start)} – ${fmt(end)}`;
  return fmt(start ?? end ?? "");
}

export function formatShortPeriod(end: string | null, fallback: string): string {
  if (!end) return fallback;
  return new Date(end).toLocaleDateString("en-IN", {
    month: "short",
    year: "2-digit",
  });
}
