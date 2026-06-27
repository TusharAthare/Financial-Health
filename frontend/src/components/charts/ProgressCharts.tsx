import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatPercent, formatShortPeriod } from "@/lib/format";
import type { ReportSummaryItem } from "@/types/api";

interface SavingsRateChartProps {
  data: ReportSummaryItem[];
}

export function SavingsRateChart({ data }: SavingsRateChartProps) {
  if (data.length < 1) {
    return (
      <p className="py-12 text-center text-sm text-slate-500">
        Upload a statement to track savings rate over time.
      </p>
    );
  }

  const chartData = data.map((item) => ({
    label: formatShortPeriod(item.period_end, item.original_filename),
    savingsRate: item.savings_rate ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip formatter={(value: number) => formatPercent(value)} />
        <Legend wrapperStyle={{ fontSize: "12px" }} />
        <Line
          type="monotone"
          dataKey="savingsRate"
          name="Savings rate"
          stroke="#16a34a"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

interface EmiBurdenChartProps {
  data: ReportSummaryItem[];
}

export function EmiBurdenChart({ data }: EmiBurdenChartProps) {
  if (data.length < 1) {
    return (
      <p className="py-12 text-center text-sm text-slate-500">
        EMI burden appears once recurring EMIs are detected.
      </p>
    );
  }

  const chartData = data.map((item) => ({
    label: formatShortPeriod(item.period_end, item.original_filename),
    emiBurden: item.emi_burden_pct ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
        <Tooltip formatter={(value: number) => formatPercent(value)} />
        <Legend wrapperStyle={{ fontSize: "12px" }} />
        <Bar dataKey="emiBurden" name="EMI % of income" fill="#dc2626" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

interface CategoryDriftChartProps {
  data: ReportSummaryItem[];
}

export function CategoryDriftChart({ data }: CategoryDriftChartProps) {
  const latest = data[data.length - 1];
  const drift = latest?.category_drift ?? [];

  if (drift.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-slate-500">
        Upload a second statement to see category spending changes.
      </p>
    );
  }

  const chartData = drift.map((item) => ({
    name: item.category_name,
    change: item.change_pct ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis type="number" tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
        <YAxis
          type="category"
          dataKey="name"
          width={120}
          tick={{ fontSize: 11 }}
        />
        <Tooltip formatter={(value: number) => formatPercent(value)} />
        <Bar dataKey="change" name="Change vs prior period" fill="#2563eb" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
