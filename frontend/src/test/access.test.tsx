import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { RequireAuth, RequirePermission } from '@/routes/ProtectedRoute';
import { api } from '@/services/api';
import { ME, mockFetch, renderApp } from './helpers';

function ui() {
  return (
    <Routes>
      <Route path="/login" element={<div>LOGIN PAGE</div>} />
      <Route path="/reports" element={<RequireAuth><RequirePermission permission="reports.view"><div>REPORTS</div></RequirePermission></RequireAuth>} />
      <Route path="/settings" element={<RequireAuth><RequirePermission permission="settings.view"><div>SETTINGS</div></RequirePermission></RequireAuth>} />
    </Routes>
  );
}

describe('Route protection', () => {
  it('redirects signed-out visitors to the login page', async () => {
    mockFetch(() => ({ status: 401, body: { detail: 'Not authenticated' } }));
    renderApp(ui(), '/reports');
    expect(await screen.findByText('LOGIN PAGE')).toBeInTheDocument();
  });

  it('shows pages the role may open', async () => {
    mockFetch(() => ({ body: ME }));
    renderApp(ui(), '/reports');
    expect(await screen.findByText('REPORTS')).toBeInTheDocument();
  });

  it('shows the access-restricted screen without the permission', async () => {
    mockFetch(() => ({ body: ME }));
    renderApp(ui(), '/settings');
    expect(await screen.findByText('Access restricted')).toBeInTheDocument();
    expect(screen.queryByText('SETTINGS')).not.toBeInTheDocument();
  });
});

describe('API client', () => {
  it('sends the CSRF token on unsafe requests only', async () => {
    document.cookie = 'nec_csrf=token-123';
    const calls = mockFetch(() => ({ body: {} }));
    await api('/alerts');
    await api('/alerts/read-all', { method: 'POST' });
    expect((calls[0].init!.headers as Record<string, string>)['X-CSRF-Token']).toBeUndefined();
    expect((calls[1].init!.headers as Record<string, string>)['X-CSRF-Token']).toBe('token-123');
    expect(calls[1].init!.credentials).toBe('same-origin');
  });

  it('turns error responses into readable messages', async () => {
    mockFetch(() => ({ status: 403, body: { detail: 'You do not have permission to perform this action' } }));
    await expect(api('/users')).rejects.toThrow('You do not have permission to perform this action');
  });
});
