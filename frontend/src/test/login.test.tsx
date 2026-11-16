import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router-dom';
import Login from '@/pages/Login';
import { ME, mockFetch, renderApp } from './helpers';

function ui() {
  return <Routes><Route path="/login" element={<Login />} /><Route path="/" element={<div>HOME PAGE</div>} /></Routes>;
}

describe('Login page', () => {
  it('validates the form before calling the server', async () => {
    const calls = mockFetch(() => ({ status: 401, body: { detail: 'Not authenticated' } }));
    renderApp(ui(), '/login');
    await userEvent.click(await screen.findByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(calls.filter((c) => c.url.includes('/auth/login'))).toHaveLength(0);
  });

  it('shows the server error for wrong credentials', async () => {
    mockFetch((url) => (url.includes('/auth/login') ? { status: 401, body: { detail: 'Incorrect e-mail or password.' } } : { status: 401, body: { detail: 'Not authenticated' } }));
    renderApp(ui(), '/login');
    await userEvent.type(await screen.findByPlaceholderText('name@company.com'), 'viewer@example.com');
    await userEvent.type(screen.getByPlaceholderText('Enter your password'), 'wrong');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect e-mail or password.');
  });

  it('signs in, sends the AJAX header and redirects', async () => {
    const calls = mockFetch((url) => (url.includes('/auth/login') ? { body: ME } : { status: 401, body: { detail: 'Not authenticated' } }));
    renderApp(ui(), '/login');
    await userEvent.type(await screen.findByPlaceholderText('name@company.com'), 'viewer@example.com');
    await userEvent.type(screen.getByPlaceholderText('Enter your password'), 'Secret-Passw0rd!');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(screen.getByText('HOME PAGE')).toBeInTheDocument());
    const login = calls.find((c) => c.url.includes('/auth/login'))!;
    const headers = login.init!.headers as Record<string, string>;
    expect(headers['X-Requested-With']).toBe('XMLHttpRequest');
    expect(JSON.parse(login.init!.body as string)).toEqual({ email: 'viewer@example.com', password: 'Secret-Passw0rd!' });
  });

  it('toggles password visibility', async () => {
    mockFetch(() => ({ status: 401, body: { detail: 'Not authenticated' } }));
    renderApp(ui(), '/login');
    const input = await screen.findByPlaceholderText('Enter your password');
    expect(input).toHaveAttribute('type', 'password');
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');
  });
});
