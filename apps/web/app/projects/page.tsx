import Link from 'next/link';
import { listProjects } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { formatAmount, formatDate } from '@/lib/format';

const STATUS_LABEL: Record<string, string> = {
  active: 'Активен',
  completed: 'Завершён',
  archived: 'Архив',
};

export default async function ProjectsPage() {
  const projects = await listProjects();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Проекты</h1>
      {projects.length === 0 ? (
        <Card>
          <CardContent className="text-muted-fg">
            Пока нет проектов. Создай первый через Telegram-бот командой /newproject.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="block">
              <Card className="hover:border-accent transition-colors">
                <CardContent className="space-y-1">
                  <div className="font-medium">{p.name}</div>
                  <div className="text-sm text-muted-fg">
                    {STATUS_LABEL[p.status] || p.status} · {formatDate(p.created_at)}
                  </div>
                  {p.budget_minor !== null && (
                    <div className="text-sm">
                      Бюджет: {formatAmount(p.budget_minor, p.currency)}
                    </div>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
