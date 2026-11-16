import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import AppLayout from '@/layouts/AppLayout';
import Access from '@/pages/Access';
import Cameras from '@/pages/Cameras';
import Dashboard from '@/pages/Dashboard';
import Employees from '@/pages/Employees';
import ForgotPassword from '@/pages/ForgotPassword';
import Login from '@/pages/Login';
import Modules from '@/pages/Modules';
import Monitoring from '@/pages/Monitoring';
import NotFound from '@/pages/NotFound';
import Profile from '@/pages/Profile';
import Reports from '@/pages/Reports';
import ResetPassword from '@/pages/ResetPassword';
import Settings from '@/pages/Settings';
import Users from '@/pages/Users';
import Violations from '@/pages/Violations';
import { PAGES } from '@/utils/nav';
import { RequireAuth, RequirePermission } from './ProtectedRoute';

const ELEMENTS: Record<string, JSX.Element> = {
  '/dashboard': <Dashboard />, '/monitoring': <Monitoring />, '/employees': <Employees />, '/modules': <Modules />,
  '/cameras': <Cameras />, '/access': <Access />, '/violations': <Violations />, '/reports': <Reports />,
  '/users': <Users />, '/settings': <Settings />,
};

function Home() {
  const { can } = useAuth();
  const first = PAGES.find((p) => can(p.permission));
  return <Navigate to={first ? first.path : '/profile'} replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route index element={<Home />} />
        {PAGES.map((p) => (
          <Route key={p.path} path={p.path} element={<RequirePermission permission={p.permission}>{ELEMENTS[p.path]}</RequirePermission>} />
        ))}
        <Route path="/profile" element={<Profile />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
