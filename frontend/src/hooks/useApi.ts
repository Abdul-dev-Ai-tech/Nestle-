import { useCallback, useEffect, useRef, useState } from 'react';
import { get, type Params } from '@/services/api';

interface State<T> { data: T | null; loading: boolean; error: string | null; path?: string | null }

/**
 * GET a resource; refetches when path/params change and optionally polls.
 * Pass `null` as path to skip. Polling refreshes silently (no loading flicker).
 */
export function useApi<T>(path: string | null, params?: Params, pollMs?: number) {
  const [state, setState] = useState<State<T>>({ data: null, loading: !!path, error: null });
  const key = path ? path + JSON.stringify(params ?? {}) : null;
  const paramsRef = useRef(params);
  paramsRef.current = params;

  const load = useCallback(async (silent = false, signal?: AbortSignal) => {
    if (!path) return;
    if (!silent) setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await get<T>(path, paramsRef.current, signal);
      setState({ data, loading: false, error: null, path });
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      setState((s) => ({ data: silent ? s.data : null, loading: false, error: (e as Error).message }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (!path) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    const ctrl = new AbortController();
    load(false, ctrl.signal);
    let timer: number | undefined;
    if (pollMs) {
      timer = window.setInterval(() => {
        if (!document.hidden) load(true);
      }, pollMs);
    }
    return () => {
      ctrl.abort();
      if (timer) window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, pollMs]);

  // Never hand a page the previous endpoint's payload while the new one is loading.
  const fresh = state.path === path;
  return { data: fresh ? state.data : null, loading: state.loading || (!!path && !fresh && !state.error), error: state.error, reload: () => load(true) };
}
