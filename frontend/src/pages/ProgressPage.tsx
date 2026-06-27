import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { CashFlowTrendChart } from "@/components/charts/CashFlowTrendChart";
import {
  CategoryDriftChart,
  EmiBurdenChart,
  SavingsRateChart,
} from "@/components/charts/ProgressCharts";
import { fetchReportSummary } from "@/lib/analysis-api";

export function ProgressPage() {
  const { data: summary = [], isLoading } = useQuery({
    queryKey: ["report-summary"],
    queryFn: fetchReportSummary,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Progress over time</h1>
        <p className="mt-1 text-slate-600">
          Compare spending, savings, EMI burden, and category drift across statement
          periods.
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-slate-500">Loading progress data...</p>
      )}

      {!isLoading && summary.length === 0 && (
        <section className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <p className="text-slate-600">
            Upload at least one parsed statement to see progress charts.
          </p>
          <Link
            to="/upload"
            className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline"
          >
            Go to upload
          </Link>
        </section>
      )}

      {summary.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Cash flow trend</h2>
            <CashFlowTrendChart data={summary} />
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Savings rate</h2>
            <SavingsRateChart data={summary} />
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">EMI burden</h2>
            <p className="mb-2 text-xs text-slate-500">
              EMI and loan debits as a percentage of income per period.
            </p>
            <EmiBurdenChart data={summary} />
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Category drift</h2>
            <p className="mb-2 text-xs text-slate-500">
              Largest category spending changes vs the prior period.
            </p>
            <CategoryDriftChart data={summary} />
          </section>
        </div>
      )}
    </div>
  );
}
