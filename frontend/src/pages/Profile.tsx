import { LogOut, Monitor } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Field, Spinner } from '@/components/ui/basic';
import { PasswordFields, checkNewPassword } from '@/components/ui/PasswordFields';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { api, del, post } from '@/services/api';
import { ago, avatarStyle, fmtDateTime, initials } from '@/utils/format';
import { PAGES } from '@/utils/nav';

interface SessionRow { id: number; ip: string; user_agent: string; created_at: string; last_seen_at: string; current: boolean }

export default function Profile() {
  const { me, can, logout, refresh } = useAuth();
  const scope = useScope();
  const toast = useToast();
  const navigate = useNavigate();
  const sessions = useApi<SessionRow[]>('/auth/sessions');
  const [name, setName] = useState(me?.user.full_name ?? '');
  const [current, setCurrent] = useState('');
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  if (!me) return null;
  const u = me.user;

  async function saveName() {
    try { await api('/auth/me', { method: 'PATCH', body: { full_name: name.trim() } }); toast.ok('Profile updated.'); refresh(); } catch (e) { toast.error(e); }
  }
  async function changePassword() {
    if (!current) return setError('Enter your current password.');
    const problem = checkNewPassword(pw, confirm);
    if (problem) return setError(problem);
    setError('');
    try {
      const r = await post<{ other_sessions_revoked: number }>('/auth/change-password', { current_password: current, new_password: pw });
      toast.ok(`Password updated. ${r.other_sessions_revoked} other session(s) signed out.`);
      setCurrent(''); setPw(''); setConfirm('');
      sessions.reload();
    } catch (e) { setError((e as Error).message); }
  }
  async function revoke(id: number) { try { await del(`/auth/sessions/${id}`); toast.ok('Session signed out.'); sessions.reload(); } catch (e) { toast.error(e); } }
  async function signOut() { await logout(); navigate('/login', { replace: true }); }

  return (
    <>
      <div className="ph"><div><h1>My profile</h1><p>Your account, password and signed-in devices.</p></div>
        <button className="btn dan" onClick={signOut}><LogOut size={15} /> Log out</button></div>
      <div className="g g2">
        <div className="card"><div className="cb">
          <div className="row wrap"><span className="av lg" style={avatarStyle(u.full_name)}>{initials(u.full_name)}</span>
            <div><div className="b" style={{ fontSize: 18 }}>{u.full_name}</div><div className="sm mut">{u.email}</div>
              <div className="row wrap" style={{ gap: 6, marginTop: 6 }}>{u.roles.map((r) => <span key={r.id} className="chip info">{r.name}</span>)}<span className="chip ok">Active</span></div></div></div>
          <div style={{ marginTop: 16 }}>
            <div className="kv"><span>Factory access</span><span>{u.factory_id ? scope.factories.find((f) => f.id === u.factory_id)?.name ?? '—' : 'All factories'}</span></div>
            <div className="kv"><span>Pages available</span><span>{PAGES.filter((p) => can(p.permission)).length} of {PAGES.length}</span></div>
            <div className="kv"><span>Last sign-in</span><span>{u.last_login_at ? fmtDateTime(u.last_login_at) : '—'}</span></div>
            <div className="kv"><span>Session expires when idle for</span><span>{me.session.idle_minutes} minutes</span></div>
          </div>
          <div className="row" style={{ marginTop: 14, alignItems: 'flex-end' }}>
            <div className="grow"><Field label="Display name"><input className="in" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} /></Field></div>
            <button className="btn" disabled={name.trim().length < 2 || name.trim() === u.full_name} onClick={saveName}>Save name</button>
          </div>
        </div></div>
        <div className="card"><div className="cb col" style={{ gap: 12 }}>
          <h3>Change password</h3>
          <Field label="Current password"><input className="in" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
          <PasswordFields value={pw} confirm={confirm} onChange={setPw} onConfirm={setConfirm} error={error} />
          <div><button className="btn pri" onClick={changePassword}>Update password</button></div>
          <span className="xs mut">Changing your password signs you out on every other device.</span>
        </div></div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <div className="ch" style={{ paddingBottom: 12 }}><div><h3>Signed-in devices</h3><p>Active sessions for your account</p></div></div>
        {!sessions.data ? <Spinner /> : (
          <div className="tw"><table className="tbl">
            <thead><tr><th>Device</th><th>IP address</th><th>Signed in</th><th>Last active</th><th /></tr></thead>
            <tbody>{sessions.data.map((s) => (
              <tr key={s.id}><td><Monitor size={14} /> <span className="sm">{s.user_agent.slice(0, 70) || 'Unknown device'}</span>{s.current && <span className="chip info" style={{ marginLeft: 6 }}>This device</span>}</td>
                <td className="mut">{s.ip || '—'}</td><td className="nw">{fmtDateTime(s.created_at)}</td><td className="nw">{ago(s.last_seen_at)}</td>
                <td className="r">{!s.current && <button className="btn s" onClick={() => revoke(s.id)}>Sign out</button>}</td></tr>
            ))}</tbody>
          </table></div>
        )}
      </div>
    </>
  );
}
