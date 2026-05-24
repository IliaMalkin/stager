'use client';

import { useFormState, useFormStatus } from 'react-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { loginAction, type LoginState } from './actions';

function SubmitBtn() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending} className="w-full">
      {pending ? 'Вхожу…' : 'Войти'}
    </Button>
  );
}

export default function LoginPage({
  searchParams,
}: {
  searchParams: { next?: string };
}) {
  const [state, action] = useFormState<LoginState, FormData>(loginAction, { error: null });
  return (
    <main className="min-h-screen flex items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Stager admin</CardTitle>
        </CardHeader>
        <CardContent>
          <form action={action} className="space-y-3">
            <input type="hidden" name="next" value={searchParams.next || '/projects'} />
            <div>
              <label className="text-sm text-muted-fg">Email</label>
              <Input name="email" type="email" autoComplete="email" required />
            </div>
            <div>
              <label className="text-sm text-muted-fg">Пароль</label>
              <Input name="password" type="password" autoComplete="current-password" required />
            </div>
            {state.error && (
              <div className="text-danger text-sm">{state.error}</div>
            )}
            <SubmitBtn />
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
