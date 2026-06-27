import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatInr, formatShortPeriod } from "@/lib/format";
import type { ReportSummaryItem } from "@/types/api";

interface CashFlowTrendChartProps {
  data: ReportSummaryItem[];
}

export function CashFlowTrendChart({ data }: CashFlowTrendChartProps) {
  if (data.length < 2) {
    return (
      <p className="py-12 text-center text-sm text-slate-500">
        Upload another statement to see spending trends over time.
      </p>
    );
  }

  const chartData = data.map((item) => ({
    label: formatShortPeriod(item.period_end, item.original_filename),
    income: Number(item.income),
    expense: Number(item.expense),
    net: Number(item.net_cash_flow),
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" tick={{ fontSize: 12 }} />
        <YAxis
          tick={{ fontSize: 12 }}
          tickFormatter={(value: number) =>
            new Intl.NumberFormat("en-IN", {
              notation: "compact",
              compactDisplay: "short",
            }).format(value)
          }
        />
        <Tooltip
          formatter={(value: number) => formatInr(value)}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid #e2e8f0",
            fontSize: "12px",
          }}
        />
        <Legend wrapperStyle={{ fontSize: "12px" }} />
        <Line
          type="monotone"
          dataKey="income"
          stroke="#16a34a"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="expense"
          stroke="#dc2626"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          type="monotone"
          dataKey="net"
          stroke="#2563eb"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
