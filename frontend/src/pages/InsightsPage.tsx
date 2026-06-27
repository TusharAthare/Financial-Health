import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { InsightCard } from "@/components/InsightCard";
import { fetchInsights } from "@/lib/analysis-api";
import { formatPeriodLabel } from "@/lib/format";
import { fetchStatements } from "@/lib/statements-api";
import type { InsightType } from "@/types/api";

const TYPE_FILTERS: Array<{ value: "all" | InsightType; label: string }> = [
  { value: "all", label: "All" },
  { value: "leak", label: "Leaks" },
  { value: "saving", label: "Savings" },
  { value: "suggestion", label: "Suggestions" },
];

export function InsightsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [typeFilter, setTypeFilter] = useState<"all" | InsightType>("all");

  const { data: statementsPage } = useQuery({
    queryKey: ["statements", { page_size: 100 }],
    queryFn: () => fetchStatements({ page_size: 100 }),
  });

  const parsedStatements = useMemo(
    () => (statementsPage?.results ?? []).filter((s) => s.status === "parsed"),
    [statementsPage],
  );

  const selectedStatementId = searchParams.get("statement");
  const activeStatementId = selectedStatementId
    ? Number(selectedStatementId)
    : null;

  const { data: insights = [], isLoading, isError, error } = useQuery({
    queryKey: ["insights", activeStatementId],
    queryFn: () => fetchInsights(activeStatementId ?? undefined),
  });

  const filteredInsights = useMemo(() => {
    if (typeFilter === "all") return insights;
    return insights.filter((item) => item.insight_type === typeFilter);
  }, [insights, typeFilter]);

  function handleStatementChange(value: string) {
    if (value === "all") {
      searchParams.delete("statement");
    } else {
      searchParams.set("statement", value);
    }
    setSearchParams(searchParams);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Insights</h1>
        <p className="mt-1 text-slate-600">
          Prioritized, explainable leaks and savings opportunities from your
          transaction history.
        </p>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label htmlFor="insight-statement" className="text-sm text-slate-600">
            Period
          </label>
          <select
            id="insight-statement"
            value={activeStatementId ? String(activeStatementId) : "all"}
            onChange={(event) => handleStatementChange(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
          >
            <option value="all">All periods</option>
            {parsedStatements.map((statement) => (
              <option key={statement.id} value={statement.id}>
                {formatPeriodLabel(
                  statement.period_start,
                  statement.period_end,
                  statement.original_filename,
                )}
              </option>
            ))}
          </select>
        </div>

        <div className="flex gap-2">
          {TYPE_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              onClick={() => setTypeFilter(filter.value)}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                typeFilter === filter.value
                  ? "bg-brand-600 text-white"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm text-slate-500">Loading insights...</p>}

      {isError && (
        <p className="text-sm text-red-600">{(error as Error).message}</p>
      )}

      {!isLoading && filteredInsights.length === 0 && (
        <p className="text-sm text-slate-500">
          No insights match your filters. Upload and parse statements to generate
          recommendations.
        </p>
      )}

      {!isLoading && filteredInsights.length > 0 && (
        <div className="grid gap-4">
          {filteredInsights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
        </div>
      )}
    </div>
  );
}
