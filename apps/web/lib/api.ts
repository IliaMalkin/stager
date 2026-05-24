import 'server-only';
import { getAuthToken } from './auth';
import type { Expense, Project, ProjectSummary, User } from './types';

const INTERNAL = process.env.INTERNAL_API_BASE || 'http://api:8000';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function fetchApi<T>(
  path: string,
  init: RequestInit = {},
  { auth = true }: { auth?: boolean } = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth) {
    const token = getAuthToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const res = await fetch(`${INTERNAL}/api/v1${path}`, {
    ...init,
    headers,
    cache: 'no-store',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new ApiError(res.status, text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function fetchApiBlob(path: string): Promise<Response> {
  const token = getAuthToken();
  return fetch(`${INTERNAL}/api/v1${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: 'no-store',
  });
}

// ─── Auth ────────────────────────────────────────────────────────────────

export interface LoginResult {
  access_token: string;
  expires_at: string;
}

export function login(email: string, password: string): Promise<LoginResult> {
  return fetchApi<LoginResult>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }, { auth: false });
}

export function getMe(): Promise<User> {
  return fetchApi<User>('/auth/me');
}

// ─── Projects ────────────────────────────────────────────────────────────

export function listProjects(): Promise<Project[]> {
  return fetchApi<Project[]>('/projects');
}

export function getProject(id: number): Promise<Project> {
  return fetchApi<Project>(`/projects/${id}`);
}

export interface ProjectFilters {
  from?: string;
  to?: string;
  category?: string;
  source?: string;
}

export function listExpenses(projectId: number, filters: ProjectFilters = {}): Promise<Expense[]> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v) params.set(k, v);
  }
  const qs = params.toString();
  return fetchApi<Expense[]>(`/projects/${projectId}/expenses${qs ? '?' + qs : ''}`);
}

export function getProjectSummary(id: number): Promise<ProjectSummary> {
  return fetchApi<ProjectSummary>(`/projects/${id}/report/summary`);
}

export function exportCsvUrl(id: number): string {
  return `/projects/${id}/report/export.csv`;
}

export function exportXlsxUrl(id: number): string {
  return `/projects/${id}/report/export.xlsx`;
}

export { fetchApiBlob, ApiError };
