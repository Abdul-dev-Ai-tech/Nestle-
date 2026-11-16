import { Eye, EyeOff, Lock, Mail } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Field } from '@/components/ui/basic';
import { useAuth } from '@/contexts/AuthContext';
import AuthLayout from '@/layouts/AuthLayout';
import { emailOk } from '@/utils/format';

const REMEMBER_KEY = 'nec.email';

export default function Login() {
  const { me, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState(() => localStorage.getItem(REMEMBER_KEY) ?? '');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(() => !!localStorage.getItem(REMEMBER_KEY));
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  // Only same-site paths are accepted as a post-login destination (no open redirect).
  const wanted = (location.state as { from?: string } | null)?.from ?? '/';
  const from = /^\/(?![\/\\])/.test(wanted) && !wanted.includes('\\') ? wanted : '/';

  if (me) return <Navigate to={from} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!emailOk(email.trim())) next.email = 'Enter a valid email address.';
    if (!password) next.password = 'Enter your password.';
    setErrors(next);
    if (next.email || next.password) return;
    setBusy(true);
    try {
      await login(email.trim(), password);
      if (remember) localStorage.setItem(REMEMBER_KEY, email.trim());
      else localStorage.removeItem(REMEMBER_KEY);
      navigate(from, { replace: true });
    } catch (err) {
      setErrors({ form: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Sign in" subtitle="Personnel Entry Compliance & Smart Access Control">
      <form className="col" style={{ gap: 14 }} onSubmit={submit} noValidate>
        {errors.form && <div className="banner err" role="alert" style={{ marginBottom: 0 }}>{errors.form}</div>}
        <Field label="Work email" error={errors.email}>
          <div className="inw"><Mail size={16} className="ic" />
            <input className={`in ${errors.email ? 'err' : ''}`} type="email" autoComplete="username" placeholder="name@company.com"
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </Field>
        <Field label="Password" error={errors.password}>
          <div className="inw"><Lock size={16} className="ic" />
            <input className={`in ${errors.password ? 'err' : ''}`} type={show ? 'text' : 'password'} autoComplete="current-password"
              placeholder="Enter your password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="btn gh s icn eye" onClick={() => setShow((s) => !s)} aria-label={show ? 'Hide password' : 'Show password'}>
              {show ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </Field>
        <div className="row sp">
          <label className="row sm" style={{ gap: 7, cursor: 'pointer' }}>
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Remember my email
          </label>
          <Link to="/forgot-password" className="sm b">Forgot password?</Link>
        </div>
        <button className="btn pri" style={{ height: 46 }} disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </AuthLayout>
  );
}
