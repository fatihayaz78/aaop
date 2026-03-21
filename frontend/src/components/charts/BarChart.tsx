"use client";

import {
  BarChart as RBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface BarChartProps {
  data: { name: string; value: number }[];
  color?: string;
  height?: number;
}

export default function BarChart({
  data,
  color = "var(--brand-primary)",
  height = 300,
}: BarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="name" stroke="var(--text-muted)" tick={{ fontSize: 12 }} />
        <YAxis stroke="var(--text-muted)" tick={{ fontSize: 12 }} />
        <Tooltip
          contentStyle={{
            backgroundColor: "var(--background-card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            color: "var(--text-primary)",
          }}
        />
        <Bar dataKey="value" fill={color} isAnimationActive={false} />
      </RBarChart>
    </ResponsiveContainer>
  );
}
