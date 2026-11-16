import { Info, Plus, ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { DoorChip, ErrorBanner, Field, Spinner, Switch, Tabs } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { del, patch, post, put } from '@/services/api';
import type { AiStatus, Door, FactorySettings, PPEItem } from '@/types';
import { PPE_ITEMS, PPE_LABELS } from '@/types';

type Tab = 'factory' | 'modules' | 'ppe' | 'detection' | 'doors' | 'notifications' | 'system';
const EVENTS: [string, string][] = [['ppe_violation', 'PPE violation / entry denied'], ['repeat_violation', 'Repeat violation by the same employee'], ['camera_offline', 'Camera offline'], ['door_fault', 'Door controller fault'], ['manual_override', 'Manual door override']];
const STATUS_TEXT: Record<string, [string, string]> = { simulated: ['warn', 'Simulated'], requires_training: ['bad', 'Requires training'], requires_validation: ['info', 'Requires on-site validation'], operational: ['ok', 'Operational'] };

function FactoryTab({ edit }: { edit: boolean }) {
  const scope = useScope();
  const toast = useToast();
  const f = scope.factory;
  const [form, setForm] = useState({ name: '', code: '', address: '', timezone: 'UTC' });
  const [newFactory, setNewFactory] = useState<{ name: string; code: string; timezone: string } | null>(null);
  const { me } = useAuth();
  useEffect(() => { if (f) setForm({ name: f.name, code: f.code, address: f.address, timezone: f.timezone }); }, [f]);
  if (!f) return <Spinner />;
  async function save() {
    try { await put(`/factories/${f!.id}`, { ...form, shifts: f!.shifts }); toast.ok('Factory settings saved.'); scope.reloadFactories(); } catch (e) { toast.error(e); }
  }
  async function create() {
    if (!newFactory) return;
    try { const created = await post<{ id: number }>('/factories', newFactory); toast.ok('Factory created.'); setNewFactory(null); await scope.reloadFactories(); scope.setFactoryId(created.id); } catch (e) { toast.error(e); }
  }
  return (
    <>
      <div className="card"><div className="cb">
        <div className="g g2">
          <Field label="Factory name"><input className="in" maxLength={120} disabled={!edit} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="Site code"><input className="in" maxLength={20} disabled={!edit} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
          <Field label="Address"><input className="in" maxLength={250} disabled={!edit} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
          <Field label="Time zone (IANA name)" hint="Used for “today”, shifts and daily reports, e.g. Asia/Karachi."><input className="in" maxLength={64} disabled={!edit} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} /></Field>
        </div>
        <h3 style={{ margin: '18px 0 8px' }}>Shifts</h3>
        <div className="tw"><table className="tbl"><thead><tr><th>Shift</th><th>Start</th><th>End</th></tr></thead>
          <tbody>{f.shifts.map((s) => <tr key={s.code}><td><b>Shift {s.code}</b></td><td>{s.start}</td><td>{s.end}</td></tr>)}</tbody></table></div>
        <div className="row wrap" style={{ marginTop: 14 }}>
          <button className="btn pri" disabled={!edit} onClick={save}>Save factory settings</button>
          {me?.user.factory_id === null && <button className="btn" disabled={!edit} onClick={() => setNewFactory({ name: '', code: '', timezone: f.timezone })}><Plus size={15} /> Add another factory</button>}
        </div>
      </div></div>
      {newFactory && (
        <Modal title="Add factory" onClose={() => setNewFactory(null)} footer={<><button className="btn" onClick={() => setNewFactory(null)}>Cancel</button><button className="btn pri" onClick={create}>Create factory</button></>}>
          <div className="col" style={{ gap: 12 }}>
            <Field label="Factory name"><input className="in" maxLength={120} autoFocus value={newFactory.name} onChange={(e) => setNewFactory({ ...newFactory, name: e.target.value })} /></Field>
            <Field label="Site code"><input className="in" maxLength={20} placeholder="e.g. PK-KBW" value={newFactory.code} onChange={(e) => setNewFactory({ ...newFactory, code: e.target.value.toUpperCase() })} /></Field>
            <Field label="Time zone"><input className="in" maxLength={64} value={newFactory.timezone} onChange={(e) => setNewFactory({ ...newFactory, timezone: e.target.value })} /></Field>
            <p className="xs mut">Each factory has its own modules, cameras, employees, doors, records and reports. Users can be restricted to one factory.</p>
          </div>
        </Modal>
      )}
    </>
  );
}

function ModulesTab() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const manage = can('modules.manage');
  const depts = useApi<{ id: number; name: string }[]>(scope.factoryId ? '/departments' : null, { factory_id: scope.factoryId ?? undefined });
  const [dept, setDept] = useState('');
  async function toggle(id: number, v: boolean) { try { await patch(`/modules/${id}`, { is_active: v }); scope.reloadModules(); } catch (e) { toast.error(e); } }
  async function addDept() {
    if (dept.trim().length < 2) return;
    try { await post('/departments', { name: dept.trim() }, { factory_id: scope.factoryId ?? undefined }); setDept(''); depts.reload(); } catch (e) { toast.error(e); }
  }
  async function removeDept(id: number) { try { await del(`/departments/${id}`); depts.reload(); } catch (e) { toast.error(e); } }
  return (
    <div className="g g21">
      <div className="card">
        <div className="ch" style={{ paddingBottom: 12 }}><div><h3>Module management</h3><p>Add areas as the factory grows.</p></div><Link className="btn s pri" to="/modules"><Plus size={14} /> Add or configure modules</Link></div>
        <div className="tw"><table className="tbl">
          <thead><tr><th>Module</th><th>Entry points</th><th>Required PPE</th><th>Active</th><th /></tr></thead>
          <tbody>{scope.modules.map((m) => (
            <tr key={m.id}><td><span className="dot" style={{ background: m.color, marginRight: 8 }} /><b>{m.name}</b> <span className="mut">{m.code}</span></td>
              <td>{m.entry_points.length}</td><td>{PPE_ITEMS.filter((i) => m.ppe[i].required).length} of {PPE_ITEMS.length}</td>
              <td><Switch checked={m.is_active} disabled={!manage} label={`${m.name} active`} onChange={(v) => toggle(m.id, v)} /></td>
              <td className="r"><Link className="btn s" to={`/modules?module=${m.id}`}>Configure</Link></td></tr>
          ))}</tbody>
        </table></div>
      </div>
      <div className="card"><div className="ch"><div><h3>Departments</h3><p>Used on employee records.</p></div></div>
        <div className="cb col" style={{ gap: 8 }}>
          {(depts.data ?? []).map((d) => <div key={d.id} className="li"><span className="grow">{d.name}</span><button className="btn s gh" disabled={!manage} onClick={() => removeDept(d.id)}>Remove</button></div>)}
          <div className="row"><input className="in" maxLength={80} placeholder="New department" disabled={!manage} value={dept} onChange={(e) => setDept(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addDept()} /><button className="btn" disabled={!manage} onClick={addDept}>Add</button></div>
        </div></div>
    </div>
  );
}

function PpeTab() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const manage = can('modules.manage');
  async function toggle(moduleId: number, item: PPEItem, required: boolean) {
    try { await put(`/modules/${moduleId}/ppe`, { rules: [{ item, required }] }); toast.ok('PPE requirement updated.'); scope.reloadModules(); } catch (e) { toast.error(e); }
  }
  return (
    <div className="card">
      <div className="ch" style={{ paddingBottom: 12 }}><div><h3>PPE requirements by module</h3><p>What must be detected before the door opens. Applies to new checks immediately.</p></div></div>
      <div className="tw"><table className="tbl mx">
        <thead><tr><th>Module</th>{PPE_ITEMS.map((i) => <th key={i}>{PPE_LABELS[i]}</th>)}</tr></thead>
        <tbody>{scope.modules.map((m) => (
          <tr key={m.id}><td><b>{m.name}</b></td>{PPE_ITEMS.map((i) => <td key={i}><Switch checked={m.ppe[i].required} disabled={!manage} label={`${m.name}: ${PPE_LABELS[i]}`} onChange={(v) => toggle(m.id, i, v)} /></td>)}</tr>
        ))}</tbody>
      </table></div>
    </div>
  );
}

function DetectionTab({ settings, edit, save }: { settings: FactorySettings; edit: boolean; save: (b: Partial<FactorySettings>) => void }) {
  const [threshold, setThreshold] = useState(Math.round(settings.confidence_threshold * 100));
  const ai = useApi<AiStatus>('/monitoring/status');
  return (
    <div className="g g2">
      <div className="card"><div className="cb col" style={{ gap: 14 }}>
        <div><h3>Detection confidence threshold</h3><p className="sm mut">A PPE item counts as detected only when the model’s confidence is at or above this value.</p></div>
        <div className="row"><input type="range" min={30} max={99} value={threshold} disabled={!edit} style={{ flex: 1, accentColor: '#123E73' }} aria-label="Confidence threshold"
          onChange={(e) => setThreshold(Number(e.target.value))} onMouseUp={() => save({ confidence_threshold: threshold / 100 })} onTouchEnd={() => save({ confidence_threshold: threshold / 100 })} onKeyUp={() => save({ confidence_threshold: threshold / 100 })} />
          <b className="num" style={{ width: 44, textAlign: 'right' }}>{threshold}%</b></div>
        <Field label="Evidence images"><select className="in" disabled={!edit} value={settings.evidence_policy} onChange={(e) => save({ evidence_policy: e.target.value as FactorySettings['evidence_policy'] })}><option value="violations">Store for violations only</option><option value="all">Store for every entry</option></select></Field>
        <Field label="Evidence retention" hint="Older evidence files are deleted by the retention job (see docs/SECURITY.md).">
          <select className="in" disabled={!edit} value={settings.retention_days} onChange={(e) => save({ retention_days: Number(e.target.value) })}>{[90, 180, 365, 730, 1095].map((d) => <option key={d} value={d}>{d} days</option>)}</select></Field>
        <div className="g g2">
          <Field label="Repeat violation after"><select className="in" disabled={!edit} value={settings.repeat_threshold} onChange={(e) => save({ repeat_threshold: Number(e.target.value) })}>{[2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} violations</option>)}</select></Field>
          <Field label="Within"><select className="in" disabled={!edit} value={settings.repeat_window_days} onChange={(e) => save({ repeat_window_days: Number(e.target.value) })}>{[7, 14, 30].map((n) => <option key={n} value={n}>{n} days</option>)}</select></Field>
        </div>
      </div></div>
      <div className="card"><div className="ch"><div><h3>AI model status</h3><p>What each detection class can currently do</p></div>{ai.data && <span className={`chip ${ai.data.simulated ? 'warn' : ai.data.available ? 'ok' : 'bad'}`}>{ai.data.simulated ? 'Simulation mode' : ai.data.available ? `Model ${ai.data.model_version}` : 'No model loaded'}</span>}</div>
        <div className="cb">
          {!ai.data ? <Spinner /> : PPE_ITEMS.map((i) => {
            const c = ai.data!.classes[i];
            const [cls, label] = STATUS_TEXT[c.status] ?? ['', c.status];
            return <div key={i} className="row sp" style={{ padding: '9px 0', borderBottom: '1px solid var(--line2)' }}><div><div className="b sm">{PPE_LABELS[i]}</div><div className="xs mut">{c.detail}</div></div><span className={`chip ${cls}`}>{label}</span></div>;
          })}
          <div className="note i" style={{ marginTop: 12 }}><Info size={16} /><div>No class is “operational” until a model trained on this site’s PPE has been validated. Training scripts and dataset instructions are in <b>ai_training/</b> and docs/AI_MODEL.md.</div></div>
        </div></div>
    </div>
  );
}

function DoorsTab({ edit }: { edit: boolean }) {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const doors = useApi<Door[]>(scope.factoryId ? '/access/doors' : null, { factory_id: scope.factoryId ?? undefined });
  const [approve, setApprove] = useState<Door | null>(null);
  const [confirmation, setConfirmation] = useState('');
  async function update(d: Door, body: object) { try { await patch(`/access/doors/${d.id}`, body); toast.ok('Door configuration saved.'); doors.reload(); } catch (e) { toast.error(e); doors.reload(); } }
  async function submitApproval(d: Door, on: boolean) {
    try { await post(`/access/doors/${d.id}/hardware-approval`, { approve: on, confirmation }); toast.ok(on ? 'Hardware operation approved.' : 'Approval withdrawn.'); setApprove(null); setConfirmation(''); doors.reload(); } catch (e) { toast.error(e); }
  }
  return (
    <>
      <div className="note" style={{ marginBottom: 16 }}><ShieldAlert size={16} /><div><b>Safety interlock.</b> Doors run in simulation by default. A real controller is driven only when the server enables hardware mode, the door uses a hardware adapter, and a Super Admin records an approval here. A simulated AI result can never operate a real door. See docs/SECURITY.md.</div></div>
      <div className="card">{!doors.data ? <Spinner /> : (
        <div className="tw"><table className="tbl">
          <thead><tr><th>Door</th><th>Controller</th><th>Unlock time</th><th>Power-loss mode</th><th>Auto-open on PASS</th><th>Status</th><th>Hardware</th></tr></thead>
          <tbody>{doors.data.map((d) => (
            <tr key={d.id}>
              <td><b>{d.name}</b><div className="xs mut">{d.entry_point}</div></td>
              <td><select className="in" style={{ width: 'auto', height: 34 }} disabled={!edit} value={d.adapter} onChange={(e) => update(d, { adapter: e.target.value })}><option value="simulation">Simulation</option><option value="http_relay">HTTP relay (template)</option></select></td>
              <td><select className="in" style={{ width: 'auto', height: 34 }} disabled={!edit} value={d.unlock_seconds} onChange={(e) => update(d, { unlock_seconds: Number(e.target.value) })}>{[3, 5, 8, 10, 15].map((s) => <option key={s} value={s}>{s} s</option>)}</select></td>
              <td><select className="in" style={{ width: 'auto', height: 34 }} disabled={!edit} value={d.fail_mode} onChange={(e) => update(d, { fail_mode: e.target.value })}><option value="fail_secure">Fail-secure (stays locked)</option><option value="fail_safe">Fail-safe (releases)</option></select></td>
              <td><Switch checked={d.auto_open} disabled={!edit} label={`${d.name} auto-open`} onChange={(v) => update(d, { auto_open: v })} /></td>
              <td><DoorChip door={d} /></td>
              <td>{d.hardware_active ? <span className="chip ok">Active</span> : d.adapter === 'simulation' ? <span className="chip">Simulation</span>
                : <button className="btn s" disabled={!can('access.hardware')} onClick={() => setApprove(d)}>{d.hardware_approved_at ? 'Approved' : 'Approve…'}</button>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}</div>
      {approve && (
        <Modal title={`Approve hardware operation — ${approve.name}`} onClose={() => setApprove(null)}
          footer={<><button className="btn" onClick={() => setApprove(null)}>Cancel</button>{approve.hardware_approved_at && <button className="btn" onClick={() => submitApproval(approve, false)}>Withdraw approval</button>}<button className="btn dan" onClick={() => submitApproval(approve, true)}>Approve</button></>}>
          <div className="note" style={{ marginBottom: 12 }}><ShieldAlert size={16} /><div>After approval this application can physically release this door. Confirm that the controller is wired fail-safe/fail-secure as required by the site’s fire and safety policy and has been tested in staging.</div></div>
          <Field label={`Type the door name to confirm: ${approve.name}`}><input className="in" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></Field>
        </Modal>
      )}
    </>
  );
}

export default function Settings() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const edit = can('settings.manage');
  const [tab, setTab] = useState<Tab>('factory');
  const settings = useApi<FactorySettings>(scope.factoryId ? '/settings' : null, { factory_id: scope.factoryId ?? undefined });
  const s = settings.data;
  async function save(body: Partial<FactorySettings>) {
    try { await put('/settings', body, { factory_id: scope.factoryId ?? undefined }); toast.ok('Setting saved.'); settings.reload(); } catch (e) { toast.error(e); settings.reload(); }
  }
  return (
    <>
      <PageHeader title="System settings" description="Factory details, modules, PPE rules, detection, doors and notifications."
        actions={!edit ? <span className="chip warn">Read-only for your role</span> : undefined} />
      <Tabs value={tab} onChange={setTab} tabs={[['factory', 'Factory'], ['modules', 'Modules'], ['ppe', 'PPE requirements'], ['detection', 'Detection & evidence'], ['doors', 'Door access'], ['notifications', 'Notifications'], ['system', 'System']]} />
      {settings.error && <ErrorBanner message={settings.error} onRetry={settings.reload} />}
      {tab === 'factory' && <FactoryTab edit={edit} />}
      {tab === 'modules' && <ModulesTab />}
      {tab === 'ppe' && <PpeTab />}
      {tab === 'detection' && (s ? <DetectionTab key={s.factory_id} settings={s} edit={edit} save={save} /> : <Spinner />)}
      {tab === 'doors' && <DoorsTab edit={edit} />}
      {tab === 'notifications' && (!s ? <Spinner /> : (
        <div className="card">
          <div className="ch" style={{ paddingBottom: 12 }}><div><h3>Notification settings</h3><p>In-app alerts are always recorded. E-mail delivery {s.system.smtp_configured ? 'uses the configured mail server' : 'needs a mail server (SMTP_* settings) — not configured on this server'}.</p></div></div>
          <div className="tw"><table className="tbl mx">
            <thead><tr><th>Event</th><th>Show in alert center</th><th>E-mail</th></tr></thead>
            <tbody>{EVENTS.map(([key, label]) => (
              <tr key={key}><td>{label}</td>
                {(['app', 'email'] as const).map((ch) => (
                  <td key={ch}><Switch checked={s.notifications[key]?.[ch] ?? ch === 'app'} disabled={!edit || (ch === 'email' && !s.system.smtp_configured)} label={`${label} ${ch}`}
                    onChange={(v) => save({ notifications: { ...s.notifications, [key]: { ...(s.notifications[key] ?? {}), [ch]: v } } })} /></td>
                ))}</tr>
            ))}</tbody>
          </table></div>
          <p className="xs mut" style={{ padding: '10px 16px' }}>These preferences are stored per factory. E-mail dispatch of alerts is not implemented yet (password-reset e-mail is) — see docs/STATUS.md.</p>
        </div>
      ))}
      {tab === 'system' && (!s ? <Spinner /> : (
        <div className="g g2">
          <div className="card"><div className="ch"><h3>Server configuration</h3></div><div className="cb">
            <div className="kv"><span>Environment</span><span>{s.system.environment}</span></div>
            <div className="kv"><span>AI mode</span><span>{s.system.ai_mode}</span></div>
            <div className="kv"><span>Door mode</span><span>{s.system.door_mode}{s.system.hardware_doors_enabled ? ' (hardware enabled)' : ''}</span></div>
            <div className="kv"><span>Session idle timeout</span><span>{s.system.session_idle_minutes} minutes</span></div>
            <div className="kv"><span>Maximum session length</span><span>{s.system.session_absolute_hours} hours</span></div>
            <div className="kv"><span>Maximum upload size</span><span>{s.system.max_upload_mb} MB</span></div>
            <div className="kv"><span>Mail server</span><span>{s.system.smtp_configured ? 'Configured' : 'Not configured'}</span></div>
            <p className="xs mut" style={{ marginTop: 10 }}>These values come from the server’s environment file (.env) and are changed there, not in the browser.</p>
          </div></div>
          <div className="card"><div className="ch"><h3>What is real and what is simulated</h3></div><div className="cb">
            {[['Sign-in, sessions, roles', 'Real — enforced by the server'], ['Employees, modules, records, reports', 'Real — stored in PostgreSQL'], ['Browser camera preview & capture', 'Real'], ['USB / RTSP camera relay', 'Real code — needs your cameras to verify'],
              ['PPE detection', s.system.ai_mode === 'simulation' ? 'Simulated until a trained model is loaded' : s.system.ai_mode === 'yolo' ? 'YOLO model — validate on site' : 'Disabled'], ['Door control', s.system.door_mode === 'simulation' ? 'Simulated — no physical door moves' : 'Hardware mode']].map(([a, b]) => (
              <div className="kv" key={a}><span>{a}</span><span>{b}</span></div>
            ))}
          </div></div>
        </div>
      ))}
    </>
  );
}
