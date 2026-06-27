/** Helpers for calendar-month filtering in the UI. */

export type MonthBounds = {
  year: number;
  month: number;
  from: string;
  to: string;
  label: string;
};

/**
 * Parse an HTML month input value (YYYY-MM) into API date bounds.
 */
export function parseMonthInput(value: string): MonthBounds | null {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (month < 1 || month > 12) {
    return null;
  }
  const lastDay = new Date(year, month, 0).getDate();
  const monthPad = String(month).padStart(2, "0");
  return {
    year,
    month,
    from: `${year}-${monthPad}-01`,
    to: `${year}-${monthPad}-${String(lastDay).padStart(2, "0")}`,
    label: new Date(year, month - 1, 1).toLocaleDateString("en-IN", {
      month: "short",
      year: "numeric",
    }),
  };
}

/**
 * Format year/month as value for input[type=month].
 */
export function toMonthInputValue(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

export function currentMonthInputValue(): string {
  const now = new Date();
  return toMonthInputValue(now.getFullYear(), now.getMonth() + 1);
}
