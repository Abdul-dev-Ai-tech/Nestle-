import { Lock, LogOut, Plus, Trash2 } from 'lucide-react';
import { Fragment, useState } from 'react';
import { ErrorBanner, Field, Spinner, Switch, Tabs } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { PasswordFields, checkNewPassword } from '@/components/ui/PasswordFields';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { del, patch, post, put } from '@/services/api';
import type { Permission, Role, User } from '@/types';
import { ago, avatarStyle, emailOk, initials } from '@/utils/format';

function UserForm({ roles, onClose, onSaved }: { roles: Role[]; onClose: () => void; onSaved: () => void }) {
  const { me } = useAuth();
  const scope = useScope();
  const toast = useToast();
  const assignable = roles.filter((r) => me?.is_superuser || !r.is_superuser);
  const [f, setF] = useState({ full_name: '', email: '', role_id: assignable.find((r) => r.name === 'Security Operator')?.id ?? assignable[0]?.id ?? 0, factory_id: scope.factoryId as number | null });
  const [pw, setPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const role = roles.find((r) => r.id === f.role_id);

  async function save() {
    if (f.full_name.trim().length < 2) return setError('Name is required.');
    if (!emailOk(f.email.trim())) return setError('Enter a valid email address.');
    const problem = checkNewPassword(pw, confirm);
    if (problem) return setError(problem);
    setBusy(true);
    try {
      await post('/users', { full_name: f.full_name.trim(), email: f.email.trim(), password: pw, role_ids: [f.role_id], factory_id: role?.is_superuser ? null : f.factory_id });
      toast.ok('User added.');
      onSaved();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <Modal title="Add user" onClose={onClose} footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn pri" disabled={busy} onClick={save}>Add user</button></>}>
      <div className="col" style={{ gap: 12 }}>
        <Field label="Full name"><input className="in" maxLength={120} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Work email"><input className="in" type="email" maxLength={120} placeholder="name@company.com" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
        <div className="g g2">
          <Field label="Role"><select className="in" value={f.role_id} onChange={(e) => setF({ ...f, role_id: Number(e.target.value) })}>{assignable.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>
          <Field label="Factory" hint={role?.is_superuser ? 'Super Admins can access every factory.' : undefined}>
            <select className="in" disabled={role?.is_superuser || scope.factories.length < 2} value={f.factory_id ?? ''} onChange={(e) => setF({ ...f, factory_id: Number(e.target.value) })}>
              {scope.factories.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </Field>
        </div>
        <PasswordFields value={pw} confirm={confirm} onChange={setPw} onConfirm={setConfirm} />
        <p className="xs mut">Give this initial password to the user through a secure channel and ask them to change it after signing in.</p>
        {error && <div className="errt" role="alert">{error}</div>}
      </div>
    </Modal>
  );
}

function UsersTab({ users, roles, reload }: { users: User[]; roles: Role[]; reload: () => void }) {
  const { me, can } = useAuth();
  const scope = useScope();
  const toast = useToast();
  const manage = can('users.manage');
  async function update(u: User, body: object, msg: string) {
    try { await patch(`/users/${u.id}`, body); toast.ok(msg); reload(); } catch (e) { toast.error(e); reload(); }
  }
  async function revoke(u: User) {
    try { const r = await post<{ revoked: number }>(`/users/${u.id}/revoke-sessions`); toast.ok(`${r.revoked} session(s) signed out for ${u.full_name}.`); } catch (e) { toast.error(e); }
  }
  return (
    <div className="card">
      <div className="ch" style={{ paddingBottom: 12 }}><div><h3>System users</h3><p>People who can sign in. Change a role, switch an account off or sign a user out everywhere.</p></div></div>
      <div className="tw"><table className="tbl">
        <thead><tr><th>User</th><th>Role</th><th>Factory</th><th>Last sign-in</th><th>Active</th><th /></tr></thead>
        <tbody>
          {users.map((u) => {
            const self = u.id === me?.user.id;
            const locked = !manage || self || (u.role === 'Super Admin' && !me?.is_superuser);
            return (
              <tr key={u.id}>
                <td><div className="row"><span className="av" style={avatarStyle(u.full_name)}>{initials(u.full_name)}</span>
                  <div><div className="b">{u.full_name}{self && <span className="chip info" style={{ marginLeft: 6 }}>You</span>}</div><div className="xs mut">{u.email}</div></div></div></td>
                <td><select className="in" style={{ width: 'auto', height: 34 }} disabled={locked} value={u.roles[0]?.id ?? ''} aria-label={`Role of ${u.full_name}`}
                  onChange={(e) => update(u, { role_ids: [Number(e.target.value)] }, 'Role updated.')}>
                  {roles.filter((r) => me?.is_superuser || !r.is_superuser || u.roles.some((x) => x.id === r.id)).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select></td>
                <td>{u.factory_id ? scope.factories.find((f) => f.id === u.factory_id)?.name ?? `#${u.factory_id}` : <span className="chip">All factories</span>}</td>
                <td className="nw">{ago(u.last_login_at)}</td>
                <td><Switch checked={u.is_active} disabled={locked} label={`${u.full_name} active`} onChange={(v) => update(u, { is_active: v }, v ? 'Account activated.' : 'Account deactivated and signed out.')} /></td>
                <td className="r"><button className="btn s" disabled={!manage || self} onClick={() => revoke(u)} title="Sign this user out of every device"><LogOut size={13} /> Sign out</button></td>
              </tr>
            );
          })}
        </tbody>
      </table></div>
    </div>
  );
}

function RolesTab({ roles, permissions, reload }: { roles: Role[]; permissions: Permission[]; reload: () => void }) {
  const { can, refresh } = useAuth();
  const toast = useToast();
  const edit = can('roles.manage');
  const [adding, setAdding] = useState<{ name: string; description: string } | null>(null);
  const categories = [...new Set(permissions.map((p) => p.category))];

  async function toggle(role: Role, code: string, on: boolean) {
    const next = on ? [...role.permissions, code] : role.permissions.filter((c) => c !== code);
    try { await put(`/roles/${role.id}/permissions`, { permissions: next }); toast.ok(`Permission updated for ${role.name}.`); reload(); refresh(); } catch (e) { toast.error(e); }
  }
  async function create() {
    if (!adding || adding.name.trim().length < 3) return toast.toast('Role name is required.', 'bad');
    try { await post('/roles', { name: adding.name.trim(), description: adding.description.trim(), permissions: ['dashboard.view'] }); toast.ok('Role created. Tick its permissions below.'); setAdding(null); reload(); } catch (e) { toast.error(e); }
  }
  async function remove(role: Role) {
    try { await del(`/roles/${role.id}`); toast.ok('Role deleted.'); reload(); } catch (e) { toast.error(e); }
  }

  return (
    <>
      {!edit && <div className="note" style={{ marginBottom: 16 }}><Lock size={16} /><div>Read-only for your role. Only a Super Admin can change the permission matrix.</div></div>}
      <div className="g g3" style={{ marginBottom: 16 }}>
        {roles.map((r) => (
          <div className="card" key={r.id}><div className="cb">
            <div className="row sp"><b>{r.name}</b><span className="chip">{r.user_count} user{r.user_count === 1 ? '' : 's'}</span></div>
            <div className="sm mut" style={{ marginTop: 4, minHeight: 36 }}>{r.description || 'Custom role'}</div>
            <div className="row sp" style={{ marginTop: 8 }}><span className="xs mut">{r.permissions.length} of {permissions.length} permissions{r.is_system ? ' · built-in' : ''}</span>
              {!r.is_system && edit && <button className="btn s gh icn" aria-label={`Delete role ${r.name}`} onClick={() => remove(r)}><Trash2 size={14} /></button>}</div>
          </div></div>
        ))}
        {edit && <div className="card" style={{ borderStyle: 'dashed', display: 'grid', placeItems: 'center', boxShadow: 'none', background: 'transparent' }}><button className="btn" onClick={() => setAdding({ name: '', description: '' })}><Plus size={15} /> Add custom role</button></div>}
      </div>
      <div className="card">
        <div className="ch" style={{ paddingBottom: 12 }}><div><h3>Permission matrix</h3><p>{edit ? 'Tick or untick to change access. Super Admin always has full access.' : 'Current access per role.'} Every permission is enforced by the server on each request.</p></div></div>
        <div className="tw"><table className="tbl mx">
          <thead><tr><th>Permission</th>{roles.map((r) => <th key={r.id}>{r.name}</th>)}</tr></thead>
          <tbody>
            {categories.map((cat) => (
              <Fragment key={cat}>
                <tr><td colSpan={roles.length + 1} className="xs b mut" style={{ background: '#FCFAF6', textAlign: 'left' }}>{cat.toUpperCase()}</td></tr>
                {permissions.filter((p) => p.category === cat).map((p) => (
                  <tr key={p.code}><td>{p.description}<div className="xs mut">{p.code}</div></td>
                    {roles.map((r) => <td key={r.id}><input type="checkbox" aria-label={`${r.name}: ${p.description}`} checked={r.is_superuser || r.permissions.includes(p.code)} disabled={!edit || r.is_superuser} onChange={(e) => toggle(r, p.code, e.target.checked)} /></td>)}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table></div>
      </div>
      {adding && (
        <Modal title="Add custom role" onClose={() => setAdding(null)} footer={<><button className="btn" onClick={() => setAdding(null)}>Cancel</button><button className="btn pri" onClick={create}>Create role</button></>}>
          <div className="col" style={{ gap: 12 }}>
            <Field label="Role name"><input className="in" maxLength={60} autoFocus value={adding.name} onChange={(e) => setAdding({ ...adding, name: e.target.value })} /></Field>
            <Field label="Description"><input className="in" maxLength={250} value={adding.description} onChange={(e) => setAdding({ ...adding, description: e.target.value })} /></Field>
          </div>
        </Modal>
      )}
    </>
  );
}

export default function Users() {
  const { can } = useAuth();
  const [tab, setTab] = useState<'users' | 'roles'>('users');
  const [adding, setAdding] = useState(false);
  const users = useApi<User[]>('/users');
  const roles = useApi<Role[]>('/roles');
  const permissions = useApi<Permission[]>('/permissions');
  const ready = users.data && roles.data && permissions.data;
  return (
    <>
      <PageHeader title="User management" description="Who can sign in, and what each role is allowed to see and do."
        actions={<button className="btn pri" disabled={!can('users.manage') || !roles.data} onClick={() => setAdding(true)}><Plus size={16} /> Add user</button>} />
      <Tabs value={tab} onChange={setTab} tabs={[['users', `Users${users.data ? ` (${users.data.length})` : ''}`], ['roles', 'Roles & permissions']]} />
      {(users.error || roles.error) && <ErrorBanner message={users.error ?? roles.error ?? ''} onRetry={() => { users.reload(); roles.reload(); }} />}
      {!ready ? <Spinner /> : tab === 'users'
        ? <UsersTab users={users.data!} roles={roles.data!} reload={() => { users.reload(); roles.reload(); }} />
        : <RolesTab roles={roles.data!} permissions={permissions.data!} reload={roles.reload} />}
      {adding && roles.data && <UserForm roles={roles.data} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); users.reload(); roles.reload(); }} />}
    </>
  );
}
