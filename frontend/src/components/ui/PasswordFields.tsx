import { Field } from './basic';
import { passwordScore } from '@/utils/format';

const LABELS = ['Too weak', 'Too weak', 'Weak', 'Fair', 'Good', 'Strong'];

/** New-password + confirmation inputs with a strength meter matching the server policy. */
export function PasswordFields({ value, confirm, onChange, onConfirm, error }: {
  value: string; confirm: string; onChange: (v: string) => void; onConfirm: (v: string) => void; error?: string;
}) {
  const score = passwordScore(value);
  return (
    <>
      <Field label="New password">
        <input className="in" type="password" autoComplete="new-password" value={value} onChange={(e) => onChange(e.target.value)} />
        <div className="meter"><i style={{ width: `${score * 20}%`, background: score < 3 ? 'var(--fail)' : score < 5 ? 'var(--warn)' : 'var(--pass)' }} /></div>
        <span className="xs mut">{value ? `${LABELS[score]} — ` : ''}10+ characters with upper and lower case, a number and a symbol.</span>
      </Field>
      <Field label="Confirm new password" error={error}>
        <input className={`in ${error ? 'err' : ''}`} type="password" autoComplete="new-password" value={confirm} onChange={(e) => onConfirm(e.target.value)} />
      </Field>
    </>
  );
}

export function checkNewPassword(value: string, confirm: string): string {
  if (passwordScore(value) < 5) return 'Password does not meet the policy yet.';
  if (value !== confirm) return 'Passwords do not match.';
  return '';
}
