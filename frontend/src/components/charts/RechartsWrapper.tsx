"use client";

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const tooltipStyle = {
  backgroundColor: "var(--background-card)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  color: "var(--text-primary)",
};

interface ChartProps {
  data: Record<string, unknown>[];
  xKey: string;
  yKey: string;
  color?: string;
  height?: number;
  type?: "line" | "bar";
  title?: string;
}

export default function RechartsWrapper({
  data,
  xKey,
  yKey,
  color = "#1f6feb",
  height = 250,
  type = "line",
  title,
}: ChartProps) {
  const Chart = type === "bar" ? BarChart : LineChart;

  return (
    <div>
      {title && (
        <p className="text-xs font-medium mb-2" style={{ color: "var(--text-secondary)" }}>
          {title}
        </p>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <Chart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey={xKey} stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
          <YAxis stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
          <Tooltip contentStyle={tooltipStyle} />
          {type === "bar" ? (
            <Bar dataKey={yKey} fill={color} isAnimationActive={false} />
          ) : (
            <Line
              type="monotone"
              dataKey={yKey}
              stroke={color}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}
