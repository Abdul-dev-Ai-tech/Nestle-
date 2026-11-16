import { useCallback, useState } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Splash } from '@/components/ui/Splash';
import { AuthProvider } from '@/contexts/AuthContext';
import { ScopeProvider } from '@/contexts/ScopeContext';
import { ToastProvider } from '@/contexts/ToastContext';
import AppRoutes from '@/routes';

const SPLASH_KEY = 'nec.splash';

export default function App() {
  // The branded loading screen plays once per browser session.
  const [splash, setSplash] = useState(() => sessionStorage.getItem(SPLASH_KEY) !== '1');
  const done = useCallback(() => { sessionStorage.setItem(SPLASH_KEY, '1'); setSplash(false); }, []);
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ToastProvider>
        <AuthProvider>
          <ScopeProvider>
            {splash && <Splash onDone={done} />}
            <AppRoutes />
          </ScopeProvider>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
