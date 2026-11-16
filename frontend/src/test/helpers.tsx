import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';
import { ToastProvider } from '@/contexts/ToastContext';
import type { Me } from '@/types';

export const ME: Me = {
  user: { id: 5, email: 'viewer@example.com', full_name: 'Mehwish Tariq', is_active: true, factory_id: 1, roles: [{ id: 5, name: 'Viewer' }], role: 'Viewer', last_login_at: null, created_at: '2026-01-01T00:00:00Z' },
  permissions: ['dashboard.view', 'reports.view'], is_superuser: false, environment: 'test', session: { id: 1, expires_at: '2030-01-01T00:00:00Z', idle_minutes: 30 },
};

type Handler = (url: string, init?: RequestInit) => { status?: number; body: unknown };

/** Replace global fetch with a small router. Returns the list of recorded calls. */
export function mockFetch(handler: Handler) {
  const calls: { url: string; init?: RequestInit }[] = [];
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    const { status = 200, body } = handler(url, init);
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  }) as typeof fetch;
  return calls;
}

export function renderApp(ui: ReactElement, route = '/') {
  return render(<MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ToastProvider><AuthProvider>{ui}</AuthProvider></ToastProvider></MemoryRouter>);
}
