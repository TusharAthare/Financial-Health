import { useQuery } from "@tanstack/react-query";

import { fetchRecurringPatterns } from "@/lib/analysis-api";
import type { RecurringPattern } from "@/types/api";

function formatAmount(value: string): string {
  const num = Number(value);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Math.abs(num));
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function patternTypeLabel(type: RecurringPattern["pattern_type"]): string {
  const labels: Record<RecurringPattern["pattern_type"], string> = {
    subscription: "Subscription",
    autopay: "Autopay",
    emi: "EMI",
    loan: "Loan",
  };
  return labels[type] ?? type;
}

function cadenceLabel(cadence: RecurringPattern["cadence"]): string {
  const labels: Record<RecurringPattern["cadence"], string> = {
    weekly: "Weekly",
    biweekly: "Bi-weekly",
    monthly: "Monthly",
    quarterly: "Quarterly",
  };
  return labels[cadence] ?? cadence;
}

export function RecurringPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["recurring"],
    queryFn: fetchRecurringPatterns,
  });

  const patterns = data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Recurring & EMIs</h1>
        <p className="mt-1 text-slate-600">
          Subscriptions, autopay mandates, and EMIs detected from your transaction
          history with explainable evidence.
        </p>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading patterns...</p>}

      {isError && (
        <p className="text-sm text-red-600">{(error as Error).message}</p>
      )}

      {!isLoading && patterns.length === 0 && (
        <p className="text-sm text-slate-500">
          No recurring patterns detected yet. Upload statements with at least three
          similar debits from the same merchant.
        </p>
      )}

      {!isLoading && patterns.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {patterns.map((pattern) => (
            <article
              key={pattern.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold text-slate-900">
                  {pattern.normalized_merchant}
                </h2>
                <span className="shrink-0 rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700">
                  {patternTypeLabel(pattern.pattern_type)}
                </span>
              </div>

              <dl className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Expected amount</dt>
                  <dd className="font-medium text-slate-900">
                    {formatAmount(pattern.expected_amount)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Cadence</dt>
                  <dd className="text-slate-900">{cadenceLabel(pattern.cadence)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Next expected</dt>
                  <dd className="text-slate-900">
                    {formatDate(pattern.next_expected_date)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Amount variance</dt>
                  <dd className="text-slate-900">
                    {pattern.amount_variance_pct.toFixed(1)}%
                  </dd>
                </div>
              </dl>

              {pattern.evidence && (
                <details className="mt-4">
                  <summary className="cursor-pointer text-xs font-medium text-brand-600 hover:underline">
                    Why detected
                  </summary>
                  <ul className="mt-2 space-y-1 text-xs text-slate-600">
                    <li>
                      {pattern.evidence.occurrences} matching debits, avg gap{" "}
                      {pattern.evidence.avg_gap_days} days
                    </li>
                    {pattern.evidence.classification_signals?.map((signal) => (
                      <li key={signal}>• {signal.replace(/_/g, " ")}</li>
                    ))}
                  </ul>
                </details>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
