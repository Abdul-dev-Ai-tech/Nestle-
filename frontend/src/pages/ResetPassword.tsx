import { Check } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { PasswordFields, checkNewPassword } from '@/components/ui/PasswordFields';
import AuthLayout from '@/layouts/AuthLayout';
import { post } from '@/services/api';

export default function ResetPassword() {
  const token = useSearchParams()[0].get('token') ?? '';
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const problem = checkNewPassword(pw, confirm);
    setError(problem);
    if (problem) return;
    setBusy(true);
    try {
      await post('/auth/reset-password', { token, new_password: pw });
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <AuthLayout title="Reset link missing" subtitle="Open the link from your e-mail again, or request a new one.">
        <Link className="btn pri" to="/forgot-password">Request a new link</Link>
      </AuthLayout>
    );
  }
  if (done) {
    return (
      <AuthLayout title="Password updated" subtitle="You have been signed out everywhere. Sign in with your new password.">
        <div className="col" style={{ gap: 14 }}>
          <div className="res p" style={{ fontSize: 16, letterSpacing: 0, flexDirection: 'row', justifyContent: 'center' }}><Check size={18} /> Password reset complete</div>
          <Link className="btn pri" style={{ height: 46 }} to="/login">Back to sign in</Link>
        </div>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title="Reset password" subtitle="Choose a new password for your account.">
      <form className="col" style={{ gap: 14 }} onSubmit={submit} noValidate>
        <PasswordFields value={pw} confirm={confirm} onChange={setPw} onConfirm={setConfirm} error={error} />
        <button className="btn pri" style={{ height: 46 }} disabled={busy}>{busy ? 'Updating…' : 'Update password'}</button>
        <Link to="/login" className="sm b">← Back to sign in</Link>
      </form>
    </AuthLayout>
  );
}
