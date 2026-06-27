/** Readable labels for common UPI bank suffixes. */
const UPI_BANK_LABELS: Record<string, string> = {
  YES: "Yes Bank",
  YBL: "Yes Bank",
  AXIS: "Axis Bank",
  HDFC: "HDFC Bank",
  ICICI: "ICICI Bank",
  SBI: "SBI",
  KOTAK: "Kotak",
  PNB: "PNB",
  OKAXIS: "Axis (Google Pay)",
  OKBIZAXIS: "Axis (GPay business)",
  OKBIZAX: "Axis (GPay business)",
  OKICICI: "ICICI (Google Pay)",
  OKHDFC: "HDFC (Google Pay)",
  OKSBI: "SBI (Google Pay)",
};

export type FormattedNarration = {
  full: string;
  lines: string[];
};

/**
 * Turn a raw bank narration into short readable lines for the UI.
 */
export function formatNarration(raw: string): FormattedNarration {
  const full = raw.trim();
  if (!full) {
    return { full: "", lines: ["—"] };
  }

  if (!/^upi/i.test(full)) {
    return { full, lines: [full] };
  }

  const body = full.replace(/^UPI-/i, "").trim();
  const parts = body.split("-").map((part) => part.trim()).filter(Boolean);
  if (parts.length === 0) {
    return { full, lines: [full] };
  }

  const lines: string[] = [];
  const payee = parts[0];
  if (payee) {
    lines.push(payee);
  }

  for (const part of parts.slice(1)) {
    if (part.includes("@")) {
      lines.push(part.toLowerCase());
      continue;
    }

    const bankLabel = UPI_BANK_LABELS[part.toUpperCase()];
    if (bankLabel) {
      lines.push(bankLabel);
      continue;
    }

    if (/^\d{8,}$/.test(part)) {
      lines.push(`Ref ${part}`);
      continue;
    }

    lines.push(part);
  }

  return { full, lines: lines.length > 0 ? lines : [full] };
}
