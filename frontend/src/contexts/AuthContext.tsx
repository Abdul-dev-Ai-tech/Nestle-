import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, get, post } from '@/services/api';
import type { Me } from '@/types';

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await get<Me>('/auth/me'));
    } catch (e) {
      if (!(e instanceof ApiError) || e.status === 401) setMe(null);
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
    const expired = () => setMe(null);
    window.addEventListener('auth:expired', expired);
    return () => window.removeEventListener('auth:expired', expired);
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const data = await post<Me>('/auth/login', { email, password });
    setMe(data);
    return data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await post('/auth/logout');
    } catch { /* session may already be gone */ }
    setMe(null);
  }, []);

  // UI convenience only — every permission is enforced again by the API.
  const can = useCallback((permission: string) => !!me && (me.is_superuser || me.permissions.includes(permission)), [me]);

  const value = useMemo(() => ({ me, loading, login, logout, refresh, can }), [me, loading, login, logout, refresh, can]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
