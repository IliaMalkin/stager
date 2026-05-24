import { getProject, getProjectSummary, listExpenses } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CategoryPie } from '@/components/CategoryPie';
import { DailyLine } from '@/components/DailyLine';
import { ExpensesTable } from '@/components/ExpensesTable';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { CATEGORY_LABELS_RU } from '@/lib/types';
import { formatAmount } from '@/lib/format';

interface PageProps {
  params: { id: string };
  searchParams: { from?: string; to?: string; category?: string; source?: string };
}

export default async function ProjectDetailPage({ params, searchParams }: PageProps) {
  const id = Number(params.id);
  const [project, summary, expenses] = await Promise.all([
    getProject(id),
    getProjectSummary(id),
    listExpenses(id, searchParams),
  ]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{project.name}</h1>
          <p className="text-sm text-muted-fg">
            Итого: <span className="font-mono">{formatAmount(summary.total_minor, summary.currency)}</span>
            {' · '}
            {summary.count} {summary.count === 1 ? 'трата' : 'трат'}
          </p>
        </div>
        <div className="flex gap-2">
          <a href={`/projects/${id}/download?format=csv`}>
            <Button variant="outline">Скачать CSV</Button>
          </a>
          <a href={`/projects/${id}/download?format=xlsx`}>
            <Button>Скачать Excel</Button>
          </a>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>По категориям</CardTitle></CardHeader>
          <CardContent>
            <CategoryPie rows={summary.by_category} currency={summary.currency} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>По дням</CardTitle></CardHeader>
          <CardContent>
            <DailyLine rows={summary.by_day} currency={summary.currency} />
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader className="flex flex-col gap-3">
          <CardTitle>Расходы</CardTitle>
          <form className="flex flex-wrap items-end gap-2" method="get">
            <div>
              <label className="block text-xs text-muted-fg mb-1">С даты</label>
              <Input type="date" name="from" defaultValue={searchParams.from} className="w-40" />
            </div>
            <div>
              <label className="block text-xs text-muted-fg mb-1">По дату</label>
              <Input type="date" name="to" defaultValue={searchParams.to} className="w-40" />
            </div>
            <div>
              <label className="block text-xs text-muted-fg mb-1">Категория</label>
              <Select name="category" defaultValue={searchParams.category || ''}>
                <option value="">Все</option>
                {(Object.keys(CATEGORY_LABELS_RU) as Array<keyof typeof CATEGORY_LABELS_RU>).map((k) => (
                  <option key={k} value={k}>{CATEGORY_LABELS_RU[k]}</option>
                ))}
              </Select>
            </div>
            <div>
              <label className="block text-xs text-muted-fg mb-1">Источник</label>
              <Select name="source" defaultValue={searchParams.source || ''}>
                <option value="">Все</option>
                <option value="bot_photo">📷 фото</option>
                <option value="bot_text">⌨ текст</option>
                <option value="admin_web">🖥 веб</option>
              </Select>
            </div>
            <Button type="submit" variant="outline" size="sm">Применить</Button>
            <a href={`/projects/${id}`}>
              <Button type="button" variant="ghost" size="sm">Сброс</Button>
            </a>
          </form>
        </CardHeader>
        <CardContent className="p-0">
          <ExpensesTable expenses={expenses} />
        </CardContent>
      </Card>
    </div>
  );
}
