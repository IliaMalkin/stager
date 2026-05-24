'use server';

import { redirect } from 'next/navigation';
import { login as apiLogin } from '@/lib/api';
import { setAuthCookie } from '@/lib/auth';

export interface LoginState {
  error: string | null;
}

export async function loginAction(prev: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get('email') || '').trim();
  const password = String(formData.get('password') || '');
  const next = String(formData.get('next') || '/projects');
  if (!email || !password) {
    return { error: 'Введи email и пароль.' };
  }
  try {
    const result = await apiLogin(email, password);
    setAuthCookie(result.access_token, result.expires_at);
  } catch (e) {
    return { error: 'Неверный email или пароль.' };
  }
  redirect(next);
}
