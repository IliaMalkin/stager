import 'server-only';
import { cookies } from 'next/headers';

const COOKIE = 'stager_token';

export function setAuthCookie(token: string, expiresAt: string) {
  cookies().set({
    name: COOKIE,
    value: token,
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/',
    expires: new Date(expiresAt),
  });
}

export function clearAuthCookie() {
  cookies().delete(COOKIE);
}

export function getAuthToken(): string | undefined {
  return cookies().get(COOKIE)?.value;
}
