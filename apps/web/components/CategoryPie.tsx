'use client';

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import type { CategoryRow } from '@/lib/types';
import { CATEGORY_LABELS_RU } from '@/lib/types';
import { formatAmount } from '@/lib/format';

const PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#64748b',
];

interface Props {
  rows: CategoryRow[];
  currency: string;
}

export function CategoryPie({ rows, currency }: Props) {
  const data = rows.map((r) => ({
    name: CATEGORY_LABELS_RU[r.category] || r.category,
    value: r.total_minor / 100,
    raw: r,
  }));

  if (data.length === 0) {
    return <div className="text-muted-fg text-sm">Нет данных</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" outerRadius={100} label>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: number) => formatAmount(Math.round(value * 100), currency)}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
