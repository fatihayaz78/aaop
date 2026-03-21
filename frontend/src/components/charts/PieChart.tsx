"use client";

import { PieChart as RPieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = ["var(--brand-primary)", "var(--risk-low)", "var(--risk-medium)", "var(--risk-high)", "var(--text-muted)"];

interface PieChartProps {
  data: { name: string; value: number }[];
  height?: number;
}

export default function PieChart({ data, height = 300 }: PieChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RPieChart>
        <Pie data={data} cx="50%" cy="50%" outerRadius={100} dataKey="value" isAnimationActive={false}>
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: "var(--background-card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            color: "var(--text-primary)",
          }}
        />
      </RPieChart>
    </ResponsiveContainer>
  );
}
