import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { get } from '@/services/api';
import type { Factory, Module } from '@/types';
import { useAuth } from './AuthContext';

/** The factory and (optional) module the user is currently looking at. */
interface Scope {
  factories: Factory[];
  factory: Factory | null;
  factoryId: number | null;
  setFactoryId: (id: number) => void;
  modules: Module[];
  moduleId: number | null;
  setModuleId: (id: number | null) => void;
  reloadModules: () => Promise<void>;
  reloadFactories: () => Promise<void>;
  /** Query parameters to send with factory-scoped requests. */
  params: { factory_id?: number; module_id?: number };
}

const ScopeContext = createContext<Scope | null>(null);
const KEY = 'nec.factory';

export function ScopeProvider({ children }: { children: ReactNode }) {
  const { me } = useAuth();
  const [factories, setFactories] = useState<Factory[]>([]);
  const [factoryId, setFactory] = useState<number | null>(null);
  const [modules, setModules] = useState<Module[]>([]);
  const [moduleId, setModuleId] = useState<number | null>(null);

  const reloadFactories = useCallback(async () => {
    const list = await get<Factory[]>('/factories');
    setFactories(list);
    setFactory((cur) => {
      const saved = Number(localStorage.getItem(KEY));
      const pick = [cur, saved, me?.user.factory_id].find((id) => id && list.some((f) => f.id === id));
      return pick ?? list[0]?.id ?? null;
    });
  }, [me?.user.factory_id]);

  const reloadModules = useCallback(async () => {
    if (!factoryId) return;
    setModules(await get<Module[]>('/modules', { factory_id: factoryId }));
  }, [factoryId]);

  useEffect(() => {
    if (me) reloadFactories().catch(() => setFactories([]));
  }, [me, reloadFactories]);

  useEffect(() => {
    if (me && factoryId) reloadModules().catch(() => setModules([]));
  }, [me, factoryId, reloadModules]);

  const setFactoryId = useCallback((id: number) => {
    localStorage.setItem(KEY, String(id));
    setFactory(id);
    setModuleId(null);
  }, []);

  const value = useMemo<Scope>(() => ({
    factories, factory: factories.find((f) => f.id === factoryId) ?? null, factoryId, setFactoryId, modules,
    moduleId, setModuleId, reloadModules, reloadFactories,
    params: { ...(factoryId ? { factory_id: factoryId } : {}), ...(moduleId ? { module_id: moduleId } : {}) },
  }), [factories, factoryId, setFactoryId, modules, moduleId, reloadModules, reloadFactories]);

  return <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>;
}

export function useScope(): Scope {
  const ctx = useContext(ScopeContext);
  if (!ctx) throw new Error('useScope must be used inside ScopeProvider');
  return ctx;
}
