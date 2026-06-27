import { Link } from "react-router-dom";

import type { Insight } from "@/types/api";

interface InsightCardProps {
  insight: Insight;
  compact?: boolean;
}

function typeStyles(type: Insight["insight_type"]): string {
  if (type === "leak") return "border-amber-200 bg-amber-50 text-amber-800";
  if (type === "saving") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function typeLabel(type: Insight["insight_type"]): string {
  if (type === "leak") return "Leak";
  if (type === "saving") return "Saving";
  return "Suggestion";
}

function evidenceLines(evidence: Insight["evidence"]): string[] {
  const lines: string[] = [];
  if (evidence.rule) {
    lines.push(`Rule: ${String(evidence.rule).replace(/_/g, " ")}`);
  }
  if (typeof evidence.savings_rate === "number") {
    lines.push(`Savings rate: ${evidence.savings_rate.toFixed(1)}%`);
  }
  if (typeof evidence.increase_pct === "number") {
    lines.push(`Increase: ${evidence.increase_pct.toFixed(1)}%`);
  }
  if (typeof evidence.decrease_pct === "number") {
    lines.push(`Decrease: ${evidence.decrease_pct.toFixed(1)}%`);
  }
  if (typeof evidence.emi_pct_of_income === "number") {
    lines.push(`EMI share of income: ${evidence.emi_pct_of_income.toFixed(1)}%`);
  }
  if (Array.isArray(evidence.merchants) && evidence.merchants.length > 0) {
    lines.push(`Merchants: ${evidence.merchants.join(", ")}`);
  }
  if (evidence.category_name) {
    lines.push(`Category: ${String(evidence.category_name)}`);
  }
  return lines;
}

export function InsightCard({ insight, compact = false }: InsightCardProps) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-slate-900">{insight.title}</h3>
          <p className={`mt-2 text-sm ${compact ? "line-clamp-2" : ""} text-slate-600`}>
            {insight.message}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-medium ${typeStyles(insight.insight_type)}`}
        >
          {typeLabel(insight.insight_type)}
        </span>
      </div>

      {!compact && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs font-medium text-brand-600 hover:underline">
            Why flagged
          </summary>
          <ul className="mt-2 space-y-1 text-xs text-slate-600">
            {evidenceLines(insight.evidence).map((line) => (
              <li key={line}>• {line}</li>
            ))}
            {evidenceLines(insight.evidence).length === 0 && (
              <li>• See raw evidence below</li>
            )}
          </ul>
          <pre className="mt-2 overflow-x-auto rounded-md bg-slate-50 p-2 text-xs text-slate-600">
            {JSON.stringify(insight.evidence, null, 2)}
          </pre>
        </details>
      )}
    </article>
  );
}

export function InsightPreviewList({
  insights,
  statementId,
}: {
  insights: Insight[];
  statementId?: number;
}) {
  const preview = insights.slice(0, 3);
  const insightsLink = statementId
    ? `/insights?statement=${statementId}`
    : "/insights";

  if (preview.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No insights yet for this period. Upload and parse a statement to generate
        explainable recommendations.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {preview.map((insight) => (
        <InsightCard key={insight.id} insight={insight} compact />
      ))}
      {insights.length > 3 && (
        <Link
          to={insightsLink}
          className="inline-block text-sm font-medium text-brand-600 hover:underline"
        >
          View all {insights.length} insights
        </Link>
      )}
    </div>
  );
}
