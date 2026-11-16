/** Thin fetch wrapper: same-origin cookies, CSRF header, JSON errors. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const BASE = '/api/v1';

function csrfToken(): string {
  const hit = document.cookie.split('; ').find((c) => c.startsWith('nec_csrf='));
  return hit ? decodeURIComponent(hit.split('=')[1]) : '';
}

export type Params = Record<string, string | number | boolean | null | undefined>;

export function withParams(path: string, params?: Params): string {
  if (!params) return path;
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '' && v !== 'all') q.set(k, String(v));
  });
  const s = q.toString();
  return s ? `${path}?${s}` : path;
}

interface Options { method?: string; body?: unknown; form?: FormData; params?: Params; signal?: AbortSignal }

async function request(path: string, opts: Options = {}): Promise<Response> {
  const method = opts.method ?? 'GET';
  const headers: Record<string, string> = { 'X-Requested-With': 'XMLHttpRequest' };
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken();
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(BASE + withParams(path, opts.params), { method, headers, body, credentials: 'same-origin', signal: opts.signal });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running.');
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === 'string') message = data.detail;
    } catch { /* non-JSON error body */ }
    if (res.status === 401 && !path.startsWith('/auth/login')) window.dispatchEvent(new Event('auth:expired'));
    throw new ApiError(res.status, message);
  }
  return res;
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const res = await request(path, opts);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const get = <T>(path: string, params?: Params, signal?: AbortSignal) => api<T>(path, { params, signal });
export const post = <T>(path: string, body?: unknown, params?: Params) => api<T>(path, { method: 'POST', body, params });
export const put = <T>(path: string, body?: unknown, params?: Params) => api<T>(path, { method: 'PUT', body, params });
export const patch = <T>(path: string, body?: unknown) => api<T>(path, { method: 'PATCH', body });
export const del = <T>(path: string) => api<T>(path, { method: 'DELETE' });
export const postForm = <T>(path: string, form: FormData) => api<T>(path, { method: 'POST', form });

export async function getBlob(path: string, params?: Params): Promise<Blob> {
  return (await request(path, { params })).blob();
}

/** Download a server-generated file (e.g. CSV export) using the session cookie. */
export async function download(path: string, params: Params, fallbackName: string): Promise<void> {
  const res = await request(path, { params });
  const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const apiUrl = (path: string, params?: Params) => BASE + withParams(path, params);
