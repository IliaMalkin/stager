import Link from 'next/link';
import { logoutAction } from './actions';
import { getMe } from '@/lib/api';
import { Button } from '@/components/ui/button';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  let me;
  try {
    me = await getMe();
  } catch {
    me = null;
  }
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-border bg-bg">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link href="/projects" className="font-semibold">Stager</Link>
          <div className="flex items-center gap-3 text-sm text-muted-fg">
            <span>{me?.email || me?.full_name || ''}</span>
            <form action={logoutAction}>
              <Button variant="ghost" size="sm" type="submit">Выйти</Button>
            </form>
          </div>
        </div>
      </header>
      <main className="max-w-6xl mx-auto w-full px-6 py-6 flex-1">{children}</main>
    </div>
  );
}
