'use client';

import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { DayRow } from '@/lib/types';
import { formatAmount, formatDate } from '@/lib/format';

interface Props {
  rows: DayRow[];
  currency: string;
}

export function DailyLine({ rows, currency }: Props) {
  const data = rows.map((r) => ({
    day: r.day,
    total: r.total_minor / 100,
  }));

  if (data.length === 0) {
    return <div className="text-muted-fg text-sm">Нет данных</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(214 32% 91%)" />
        <XAxis
          dataKey="day"
          tickFormatter={(d) => formatDate(d).slice(0, 5)}
          tick={{ fontSize: 12 }}
        />
        <YAxis tick={{ fontSize: 12 }} width={80} />
        <Tooltip
          labelFormatter={(d) => formatDate(d as string)}
          formatter={(value: number) => formatAmount(Math.round(value * 100), currency)}
        />
        <Line type="monotone" dataKey="total" stroke="hsl(221 83% 53%)" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
