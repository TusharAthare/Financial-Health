import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { CashFlowTrendChart } from "@/components/charts/CashFlowTrendChart";
import { CategoryDonutChart } from "@/components/charts/CategoryDonutChart";
import { InsightPreviewList } from "@/components/InsightCard";
import { useAuth } from "@/contexts/AuthContext";
import {
  createReportExport,
  fetchAvailableMonths,
  fetchInsights,
  fetchMonthlySummary,
  fetchReport,
  fetchReportSummary,
  pollAndDownloadExport,
} from "@/lib/analysis-api";
import { formatInr, formatPercent, formatPeriodLabel } from "@/lib/format";
import { currentMonthInputValue, parseMonthInput, toMonthInputValue } from "@/lib/month-period";
import { fetchStatements } from "@/lib/statements-api";

function KpiCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "positive" | "negative";
}) {
  const valueClass =
    tone === "positive"
      ? "text-emerald-600"
      : tone === "negative"
        ? "text-red-600"
        : "text-slate-900";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${valueClass}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const { data: statementsPage, isLoading: statementsLoading } = useQuery({
    queryKey: ["statements", { page_size: 100 }],
    queryFn: () => fetchStatements({ page_size: 100 }),
  });

  const parsedStatements = useMemo(
    () => (statementsPage?.results ?? []).filter((s) => s.status === "parsed"),
    [statementsPage],
  );

  const [selectedStatementId, setSelectedStatementId] = useState<number | null>(
    null,
  );
  const [viewMode, setViewMode] = useState<"statement" | "month">("month");
  const [selectedMonth, setSelectedMonth] = useState(currentMonthInputValue());

  const activeStatementId =
    selectedStatementId ?? parsedStatements[0]?.id ?? null;

  const { data: availableMonths = [] } = useQuery({
    queryKey: ["monthly-months"],
    queryFn: fetchAvailableMonths,
  });

  const monthBounds = parseMonthInput(selectedMonth);

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ["report", activeStatementId],
    queryFn: () => fetchReport(activeStatementId!),
    enabled: viewMode === "statement" && activeStatementId !== null,
  });

  const { data: monthlySummary, isLoading: monthlyLoading } = useQuery({
    queryKey: ["monthly-summary", monthBounds?.year, monthBounds?.month],
    queryFn: () => fetchMonthlySummary(monthBounds!.year, monthBounds!.month),
    enabled: viewMode === "month" && monthBounds !== null,
  });

  const { data: summary = [] } = useQuery({
    queryKey: ["report-summary"],
    queryFn: fetchReportSummary,
  });

  const { data: insights = [] } = useQuery({
    queryKey: ["insights", activeStatementId],
    queryFn: () => fetchInsights(activeStatementId ?? undefined),
    enabled: viewMode === "statement" && activeStatementId !== null,
  });

  const aggregates =
    viewMode === "month" ? monthlySummary?.aggregates : report?.aggregates;
  const displayInsights =
    viewMode === "month"
      ? (monthlySummary?.insights.map((item, index) => ({
          id: index,
          statement_id: 0,
          insight_type: item.insight_type,
          priority: item.priority,
          title: item.title,
          message: item.message,
          evidence: item.evidence,
          period_start: monthlySummary.period_start,
          period_end: monthlySummary.period_end,
          created_at: "",
        })) ?? [])
      : insights;
  const isReportLoading = viewMode === "month" ? monthlyLoading : reportLoading;

  const exportMutation = useMutation({
    mutationFn: (format: "csv" | "pdf") =>
      createReportExport(activeStatementId!, format).then((job) =>
        pollAndDownloadExport(job.id),
      ),
  });

  const netTone =
    aggregates && Number(aggregates.net_cash_flow) >= 0 ? "positive" : "negative";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Welcome{user?.first_name ? `, ${user.first_name}` : ""}
          </h1>
          <p className="mt-1 text-slate-600">
            Cash flow, category mix, and explainable insights from your statements.
          </p>
        </div>
        <div className="flex gap-3">
          <Link
            to="/upload"
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Upload statement
          </Link>
          <Link
            to="/insights"
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            All insights
          </Link>
          <Link
            to="/progress"
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Progress
          </Link>
        </div>
      </div>

      {statementsLoading && (
        <p className="text-sm text-slate-500">Loading statements...</p>
      )}

      {!statementsLoading && parsedStatements.length === 0 && (
        <section className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <p className="text-slate-600">
            No parsed statements yet. Upload a CSV or PDF to see your dashboard.
          </p>
          <Link
            to="/upload"
            className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline"
          >
            Go to upload
          </Link>
        </section>
      )}

      {parsedStatements.length > 0 && (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-slate-600">View by</span>
              <button
                type="button"
                onClick={() => setViewMode("month")}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  viewMode === "month"
                    ? "bg-brand-600 text-white"
                    : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                Calendar month
              </button>
              <button
                type="button"
                onClick={() => setViewMode("statement")}
                className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                  viewMode === "statement"
                    ? "bg-brand-600 text-white"
                    : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                Statement
              </button>
            </div>

            {viewMode === "month" ? (
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                <label htmlFor="month-select" className="text-sm text-slate-600">
                  Month
                </label>
                <input
                  id="month-select"
                  type="month"
                  value={selectedMonth}
                  onChange={(event) => setSelectedMonth(event.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
                />
                {availableMonths.length > 0 && (
                  <select
                    aria-label="Quick pick month with data"
                    value={selectedMonth}
                    onChange={(event) => setSelectedMonth(event.target.value)}
                    className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
                  >
                    {availableMonths.map((item) => (
                      <option
                        key={`${item.year}-${item.month}`}
                        value={toMonthInputValue(item.year, item.month)}
                      >
                        {item.label} ({item.transaction_count} txns)
                      </option>
                    ))}
                  </select>
                )}
                {monthBounds && (
                  <Link
                    to={`/transactions?from=${monthBounds.from}&to=${monthBounds.to}`}
                    className="text-sm font-medium text-brand-600 hover:underline"
                  >
                    View transactions
                  </Link>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <label htmlFor="statement-select" className="text-sm text-slate-600">
                  Statement period
                </label>
                <select
                  id="statement-select"
                  value={activeStatementId ?? ""}
                  onChange={(event) =>
                    setSelectedStatementId(Number(event.target.value))
                  }
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
                >
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
            )}

            {viewMode === "statement" && activeStatementId && (
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={exportMutation.isPending}
                  onClick={() => exportMutation.mutate("csv")}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Export CSV
                </button>
                <button
                  type="button"
                  disabled={exportMutation.isPending}
                  onClick={() => exportMutation.mutate("pdf")}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Export PDF
                </button>
              </div>
            )}
          </div>

          {exportMutation.isError && (
            <p className="text-sm text-red-600">
              {(exportMutation.error as Error).message}
            </p>
          )}

          {isReportLoading && (
            <p className="text-sm text-slate-500">Loading report...</p>
          )}

          {!isReportLoading && viewMode === "month" && (
            !aggregates || aggregates.transaction_count === 0
          ) && (
            <p className="text-sm text-slate-500">
              No transactions in {monthBounds?.label ?? "this month"}.
            </p>
          )}

          {aggregates && aggregates.transaction_count > 0 && (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KpiCard
                  label="Net cash flow"
                  value={formatInr(aggregates.net_cash_flow)}
                  tone={netTone}
                />
                <KpiCard
                  label="Income"
                  value={formatInr(aggregates.income)}
                  tone="positive"
                />
                <KpiCard
                  label="Expenses"
                  value={formatInr(aggregates.expense)}
                  tone="negative"
                />
                <KpiCard
                  label="Savings rate"
                  value={formatPercent(aggregates.savings_rate)}
                  hint={`${aggregates.transaction_count} transactions`}
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-900">
                    Spending by category
                  </h2>
                  <CategoryDonutChart data={aggregates.category_totals} />
                  <ul className="mt-2 space-y-1 text-sm">
                    {aggregates.category_totals.slice(0, 5).map((item) => (
                      <li
                        key={item.category_slug}
                        className="flex justify-between text-slate-600"
                      >
                        <span>{item.category_name}</span>
                        <span className="font-medium text-slate-900">
                          {formatInr(item.total)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-900">
                    Income vs expense trend
                  </h2>
                  <CashFlowTrendChart data={summary} />
                </section>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-900">
                    Recurring summary
                  </h2>
                  <dl className="mt-4 space-y-3 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-slate-500">EMI & loans</dt>
                      <dd className="font-medium text-slate-900">
                        {formatInr(aggregates.emi_total)}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-slate-500">Subscriptions & autopay</dt>
                      <dd className="font-medium text-slate-900">
                        {formatInr(aggregates.subscription_total)}
                      </dd>
                    </div>
                    <div className="flex justify-between border-t border-slate-100 pt-3">
                      <dt className="text-slate-500">Total recurring debits</dt>
                      <dd className="font-semibold text-slate-900">
                        {formatInr(aggregates.recurring_debit_total)}
                      </dd>
                    </div>
                  </dl>
                  <Link
                    to="/recurring"
                    className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline"
                  >
                    View recurring patterns
                  </Link>
                </section>

                <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-slate-900">
                      Top insights
                    </h2>
                    <Link
                      to={
                        activeStatementId
                          ? `/insights?statement=${activeStatementId}`
                          : "/insights"
                      }
                      className="text-sm font-medium text-brand-600 hover:underline"
                    >
                      View all
                    </Link>
                  </div>
                  <div className="mt-4">
                    <InsightPreviewList
                      insights={displayInsights}
                      statementId={
                        viewMode === "statement" ? activeStatementId ?? undefined : undefined
                      }
                    />
                  </div>
                </section>
              </div>
            </>
          )}

          {!isReportLoading && !aggregates && viewMode === "statement" && activeStatementId && (
            <p className="text-sm text-slate-500">
              Report not available for this statement. Re-upload or wait for
              analysis to complete.
            </p>
          )}
        </>
      )}
    </div>
  );
}
