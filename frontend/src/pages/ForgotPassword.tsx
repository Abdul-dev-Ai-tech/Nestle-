import { Mail } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Field } from '@/components/ui/basic';
import AuthLayout from '@/layouts/AuthLayout';
import { post } from '@/services/api';
import { emailOk } from '@/utils/format';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<{ message: string; dev_reset_url?: string } | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!emailOk(email.trim())) return setError('Enter a valid email address.');
    setError('');
    setBusy(true);
    try {
      setSent(await post('/auth/forgot-password', { email: email.trim() }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    const devPath = sent.dev_reset_url ? new URL(sent.dev_reset_url).pathname + new URL(sent.dev_reset_url).search : null;
    return (
      <AuthLayout title="Check your inbox" subtitle={sent.message}>
        <div className="col" style={{ gap: 14 }}>
          <div className="note i"><Mail size={16} /><div>The link is valid for a limited time and can be used once.</div></div>
          {devPath && (
            <div className="note"><div><b>Development mode.</b> No mail server is configured, so the reset link is shown here instead of being e-mailed.
              <div style={{ marginTop: 8 }}><Link className="btn s" to={devPath}>Open reset link</Link></div></div></div>
          )}
          <Link to="/login" className="sm b">← Back to sign in</Link>
        </div>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title="Forgot password" subtitle="Enter your work email and we will send a reset link.">
      <form className="col" style={{ gap: 14 }} onSubmit={submit} noValidate>
        <Field label="Work email" error={error}>
          <div className="inw"><Mail size={16} className="ic" />
            <input className={`in ${error ? 'err' : ''}`} type="email" placeholder="name@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
        </Field>
        <button className="btn pri" style={{ height: 46 }} disabled={busy}>{busy ? 'Sending…' : 'Send reset link'}</button>
        <Link to="/login" className="sm b">← Back to sign in</Link>
      </form>
    </AuthLayout>
  );
}
