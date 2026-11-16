import { AlertTriangle, Check, Info } from 'lucide-react';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

type Kind = 'info' | 'ok' | 'bad';
interface Toast { id: number; text: string; kind: Kind }
interface ToastApi { toast: (text: string, kind?: Kind) => void; ok: (text: string) => void; error: (e: unknown) => void }

const ToastContext = createContext<ToastApi | null>(null);
let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const toast = useCallback((text: string, kind: Kind = 'info') => {
    const id = ++seq;
    setItems((t) => [...t.slice(-3), { id, text, kind }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), 3800);
  }, []);
  const api = useMemo<ToastApi>(() => ({
    toast,
    ok: (text) => toast(text, 'ok'),
    error: (e) => toast(e instanceof Error ? e.message : 'Something went wrong', 'bad'),
  }), [toast]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind === 'info' ? '' : t.kind}`}>
            {t.kind === 'bad' ? <AlertTriangle size={18} /> : t.kind === 'ok' ? <Check size={18} /> : <Info size={18} />}
            <div>{t.text}</div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}
