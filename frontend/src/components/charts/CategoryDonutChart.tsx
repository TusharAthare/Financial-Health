import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { formatInr } from "@/lib/format";
import type { CategoryTotal } from "@/types/api";

const CHART_COLORS = [
  "#2563eb",
  "#7c3aed",
  "#db2777",
  "#ea580c",
  "#ca8a04",
  "#16a34a",
  "#0891b2",
  "#64748b",
];

interface CategoryDonutChartProps {
  data: CategoryTotal[];
}

export function CategoryDonutChart({ data }: CategoryDonutChartProps) {
  const chartData = data.slice(0, 8).map((item) => ({
    name: item.category_name,
    value: Number(item.total),
  }));

  if (chartData.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-slate-500">
        No categorized spending for this period.
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={chartData}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={95}
          paddingAngle={2}
        >
          {chartData.map((entry, index) => (
            <Cell
              key={entry.name}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: number) => formatInr(value)}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid #e2e8f0",
            fontSize: "12px",
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
