import { AlertTriangle, BarChart3, Camera as CameraIcon, ChevronLeft, ChevronRight, DoorOpen, Factory, Plus, ShieldCheck, Trash2, Users } from 'lucide-react';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ComplianceTrend, EntriesBars } from '@/components/charts/Charts';
import { CameraStatusChip, DoorChip, DoorVisual, Field, Kpi, ResultChip, Spinner, Switch, Tabs } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { del, patch, post, put } from '@/services/api';
import type { DashboardSummary, Module, PPEItem } from '@/types';
import { PPE_ITEMS, PPE_LABELS } from '@/types';
import { fmtPct, fmtTime } from '@/utils/format';

function ModuleForm({ onClose, onSaved }: { onClose: () => void; onSaved: (m: Module) => void }) {
  const scope = useScope();
  const [f, setF] = useState({ name: '', code: '', description: '', first_entry_point: '' });
  const [ppe, setPpe] = useState<PPEItem[]>(PPE_ITEMS.filter((i) => i !== 'beard_net'));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function save() {
    if (f.name.trim().length < 3) return setError('Module name is required.');
    if (!/^[A-Za-z0-9]{2,10}$/.test(f.code.trim())) return setError('Code must be 2–10 letters or numbers.');
    if (f.first_entry_point.trim().length < 3) return setError('Give the first entry point a name.');
    setBusy(true);
    try {
      onSaved(await post<Module>('/modules', { ...f, required_ppe: ppe }, { factory_id: scope.factoryId ?? undefined }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Add factory module" onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn pri" disabled={busy} onClick={save}>Create module</button></>}>
      <div className="g g2">
        <Field label="Module name"><input className="in" maxLength={80} placeholder="e.g. Dispatch" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Short code"><input className="in" maxLength={10} placeholder="e.g. DSP" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value.toUpperCase() })} /></Field>
      </div>
      <div className="col" style={{ marginTop: 12, gap: 12 }}>
        <Field label="Description"><input className="in" maxLength={200} placeholder="What happens in this area" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <Field label="First entry point name" hint="A door record in simulation mode is created with it. Add a camera on the Camera Management page.">
          <input className="in" maxLength={80} placeholder="e.g. Dispatch Gate 1" value={f.first_entry_point} onChange={(e) => setF({ ...f, first_entry_point: e.target.value })} />
        </Field>
      </div>
      <div className="xs mut b" style={{ margin: '14px 0 6px' }}>REQUIRED PPE</div>
      <div className="row wrap" style={{ gap: 14 }}>
        {PPE_ITEMS.map((i) => (
          <label key={i} className="row sm" style={{ gap: 6 }}>
            <input type="checkbox" checked={ppe.includes(i)} onChange={(e) => setPpe(e.target.checked ? [...ppe, i] : ppe.filter((x) => x !== i))} /> {PPE_LABELS[i]}
          </label>
        ))}
      </div>
      {error && <div className="errt" style={{ marginTop: 10 }} role="alert">{error}</div>}
    </Modal>
  );
}

function ModuleDetail({ module, onBack }: { module: Module; onBack: () => void }) {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const manage = can('modules.manage');
  const [tab, setTab] = useState<'overview' | 'eps' | 'ppe' | 'access' | 'reports'>('overview');
  const [epName, setEpName] = useState<string | null>(null);
  const sum = useApi<DashboardSummary>('/dashboard/summary', { factory_id: module.factory_id, module_id: module.id }, 10000);
  const d = sum.data;

  async function togglePpe(item: PPEItem, required: boolean) {
    try {
      await put(`/modules/${module.id}/ppe`, { rules: [{ item, required, min_confidence: module.ppe[item].min_confidence }] });
      toast.ok(`${PPE_LABELS[item]} is now ${required ? 'required' : 'not required'} in ${module.name}.`);
      scope.reloadModules();
    } catch (e) { toast.error(e); }
  }
  async function toggleActive(v: boolean) {
    try { await patch(`/modules/${module.id}`, { is_active: v }); toast.ok(v ? 'Monitoring resumed.' : 'Monitoring paused.'); scope.reloadModules(); } catch (e) { toast.error(e); }
  }
  async function addEntryPoint() {
    if (!epName || epName.trim().length < 3) return toast.toast('Entry point name is required.', 'bad');
    try { await post(`/modules/${module.id}/entry-points`, { name: epName.trim(), create_door: true }); toast.ok('Entry point added with a simulated door.'); setEpName(null); scope.reloadModules(); sum.reload(); } catch (e) { toast.error(e); }
  }
  async function removeEntryPoint(id: number) {
    try { const r = await del<{ result: string }>(`/entry-points/${id}`); toast.ok(`Entry point ${r.result}.`); scope.reloadModules(); sum.reload(); } catch (e) { toast.error(e); }
  }

  return (
    <>
      <PageHeader title={`${module.name} · ${module.code}`} description={module.description || 'Factory module'}
        actions={<><button className="btn" onClick={onBack}><ChevronLeft size={15} /> All modules</button>
          <label className="row sm" style={{ gap: 8 }}><Switch checked={module.is_active} disabled={!manage} onChange={toggleActive} label="Monitoring active" /> Monitoring active</label></>} />
      <Tabs value={tab} onChange={setTab} tabs={[['overview', 'Monitoring'], ['eps', 'Entry points & cameras'], ['ppe', 'PPE requirements'], ['access', 'Access control'], ['reports', 'Reports']]} />
      {!d ? <Spinner /> : (
        <>
          {tab === 'overview' && (
            <>
              <div className="g g4">
                <Kpi icon={Users} label="Entries today" value={d.today.entries} hint="All entry points" />
                <Kpi icon={ShieldCheck} tone="gold" label="Compliance today" value={fmtPct(d.today.compliance)} hint="Passed checks" />
                <Kpi icon={AlertTriangle} tone="bad" label="Violations today" value={d.today.failed} danger={d.today.failed > 0} hint={`${d.open_violations} open in total`} />
                <Kpi icon={CameraIcon} tone="info" label="Cameras online" value={`${d.cameras.filter((c) => c.status === 'online').length} / ${d.cameras.length}`} hint={`${d.doors.filter((x) => x.online).length} / ${d.doors.length} doors online`} />
              </div>
              <div className="g g21" style={{ marginTop: 16 }}>
                <div className="card"><div className="ch"><h3>Entries — last 14 days</h3></div><div className="cb"><EntriesBars data={d.daily.slice(-14)} height={220} /></div></div>
                <div className="card"><div className="ch"><h3>Latest activity</h3></div><div className="cb col">
                  {d.recent_entries.map((r) => <div key={r.id} className="row sp sm"><span><b>{r.employee?.full_name ?? 'Unidentified'}</b><span className="mut"> · {fmtTime(r.occurred_at)} · {r.entry_point}</span></span><ResultChip passed={r.passed} /></div>)}
                  {!d.recent_entries.length && <div className="mut sm">No entries recorded yet.</div>}
                </div></div>
              </div>
            </>
          )}
          {tab === 'eps' && (
            <div className="card">
              <div className="ch" style={{ paddingBottom: 12 }}>
                <div><h3>Entry points, cameras and doors</h3><p>Each entry point pairs a camera with a door controller.</p></div>
                <div className="row">{can('cameras.view') && <Link className="btn s" to="/cameras"><CameraIcon size={14} /> Manage cameras</Link>}
                  <button className="btn s pri" disabled={!manage} onClick={() => setEpName('')}><Plus size={14} /> Add entry point</button></div>
              </div>
              <div className="tw"><table className="tbl">
                <thead><tr><th>Entry point</th><th>Camera</th><th>Camera status</th><th>Door</th><th>Door status</th><th /></tr></thead>
                <tbody>
                  {module.entry_points.map((ep) => {
                    const cam = d.cameras.find((c) => c.entry_point_id === ep.id);
                    const door = d.doors.find((x) => x.entry_point_id === ep.id);
                    return (
                      <tr key={ep.id}><td><b>{ep.name}</b>{!ep.is_active && <span className="chip" style={{ marginLeft: 8 }}>Inactive</span>}</td>
                        <td>{cam ? `${cam.name} · ${cam.type.toUpperCase()}` : <span className="mut">No camera linked</span>}</td>
                        <td>{cam ? <CameraStatusChip camera={cam} /> : '—'}</td><td>{door?.name ?? '—'}</td><td>{door ? <DoorChip door={door} /> : '—'}</td>
                        <td className="r"><button className="btn s gh icn" disabled={!manage} aria-label={`Remove ${ep.name}`} onClick={() => removeEntryPoint(ep.id)}><Trash2 size={15} /></button></td></tr>
                    );
                  })}
                  {!module.entry_points.length && <tr><td colSpan={6} className="empty">No entry points yet.</td></tr>}
                </tbody>
              </table></div>
            </div>
          )}
          {tab === 'ppe' && (
            <div className="card"><div className="ch"><div><h3>PPE compliance requirements</h3><p>Items a person must wear to pass at this module’s entry points. Changes apply to new checks.</p></div></div>
              <div className="cb">
                {PPE_ITEMS.map((i) => (
                  <div key={i} className="row sp" style={{ padding: '11px 0', borderBottom: '1px solid var(--line2)' }}>
                    <div><div className="b">{PPE_LABELS[i]}</div><div className="xs mut">{i === 'beard_net' ? 'Checked only for employees where a beard net applies.' : 'Mandatory for every person when enabled.'}</div></div>
                    <Switch checked={module.ppe[i].required} disabled={!manage} onChange={(v) => togglePpe(i, v)} label={PPE_LABELS[i]} />
                  </div>
                ))}
                {!manage && <p className="sm mut" style={{ marginTop: 10 }}>Your role cannot change PPE rules.</p>}
              </div></div>
          )}
          {tab === 'access' && (
            <>
              <div className="g g3">
                {d.doors.map((door) => (
                  <div className="card" key={door.id}><div className="cb row"><DoorVisual door={door} />
                    <div><div className="b">{door.name}</div><div className="xs mut">{door.fail_mode.replace('_', '-')} · unlock {door.unlock_seconds}s · {door.hardware_active ? 'hardware' : 'simulation'}</div><div style={{ marginTop: 6 }}><DoorChip door={door} /></div></div></div></div>
                ))}
                {!d.doors.length && <div className="card empty" style={{ gridColumn: '1/-1' }}>No doors yet.</div>}
              </div>
              {can('access.view') && <Link className="btn" style={{ marginTop: 14 }} to="/access" onClick={() => scope.setModuleId(module.id)}><DoorOpen size={15} /> Open access control for this module</Link>}
            </>
          )}
          {tab === 'reports' && (
            <>
              <div className="card"><div className="ch"><div><h3>Compliance — last 30 days</h3><p>Share of entries that passed</p></div></div><div className="cb"><ComplianceTrend data={d.daily} height={230} /></div></div>
              {can('reports.view') && <Link className="btn" style={{ marginTop: 14 }} to="/reports" onClick={() => scope.setModuleId(module.id)}><BarChart3 size={15} /> Open full reports for this module</Link>}
            </>
          )}
        </>
      )}
      {epName !== null && (
        <Modal title="Add entry point" onClose={() => setEpName(null)} footer={<><button className="btn" onClick={() => setEpName(null)}>Cancel</button><button className="btn pri" onClick={addEntryPoint}>Add entry point</button></>}>
          <Field label="Entry point name" hint="A door controller record in simulation mode is created for it."><input className="in" autoFocus maxLength={80} placeholder="e.g. Gate C" value={epName} onChange={(e) => setEpName(e.target.value)} /></Field>
        </Modal>
      )}
    </>
  );
}

export default function Modules() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [adding, setAdding] = useState(false);
  const manage = can('modules.manage');
  const sum = useApi<DashboardSummary>(scope.factoryId ? '/dashboard/summary' : null, { factory_id: scope.factoryId ?? undefined }, 15000);
  const open = scope.modules.find((m) => m.id === Number(params.get('module')));
  if (open) return <ModuleDetail module={open} onBack={() => setParams({})} />;

  return (
    <>
      <PageHeader title="Factory modules" description={`${scope.factory?.name ?? ''} — each module has its own cameras, PPE rules, entry points, doors and reports.`}
        actions={<button className="btn pri" disabled={!manage} onClick={() => setAdding(true)}><Plus size={16} /> Add module</button>} />
      <div className="g g2">
        {scope.modules.map((m) => {
          const stat = sum.data?.by_module.find((x) => x.module_id === m.id);
          const cams = sum.data?.cameras.filter((c) => c.module_id === m.id) ?? [];
          return (
            <div key={m.id} className="card lift" style={{ borderTop: `4px solid ${m.color}` }}>
              <div className="cb">
                <div className="row sp wrap">
                  <div><h2>{m.name} <span className="mut sm">· {m.code}</span></h2><div className="sm mut">{m.description}</div></div>
                  {m.is_active ? <span className="chip ok"><span className="dot" />Monitoring</span> : <span className="chip">Inactive</span>}
                </div>
                <div className="g g4" style={{ margin: '14px 0', gap: 8 }}>
                  {[['Compliance (7 days)', fmtPct(stat?.compliance)], ['Entries (7 days)', stat?.entries ?? 0], ['Entry points', m.entry_points.length], ['Cameras linked', cams.length]].map(([l, v]) => (
                    <div key={String(l)} style={{ background: '#FBF8F2', border: '1px solid var(--line2)', borderRadius: 10, padding: '9px 10px' }}><div className="xs mut">{l}</div><div className="b num" style={{ fontSize: 17 }}>{v}</div></div>
                  ))}
                </div>
                <div className="xs mut b" style={{ marginBottom: 6 }}>REQUIRED PPE</div>
                <div className="row wrap" style={{ gap: 6 }}>
                  {PPE_ITEMS.filter((i) => m.ppe[i].required).map((i) => <span key={i} className="chip">{PPE_LABELS[i]}</span>)}
                  {!PPE_ITEMS.some((i) => m.ppe[i].required) && <span className="mut sm">No PPE rules yet</span>}
                </div>
                <div className="row wrap" style={{ marginTop: 14 }}>
                  <button className="btn pri s" onClick={() => setParams({ module: String(m.id) })}>Open module <ChevronRight size={13} /></button>
                  <button className="btn s" disabled={!m.is_active} onClick={() => { scope.setModuleId(m.id); toast.toast(`Showing data for ${m.name} across the app.`); }}>Filter whole app to this module</button>
                </div>
              </div>
            </div>
          );
        })}
        <div className="card" style={{ borderStyle: 'dashed', display: 'grid', placeItems: 'center', minHeight: 180, background: 'transparent', boxShadow: 'none' }}>
          <div style={{ textAlign: 'center', padding: 20 }}>
            <div className="mut"><Factory size={30} /></div>
            <b style={{ display: 'block', margin: '6px 0 2px' }}>Scale to new areas</b>
            <div className="sm mut" style={{ marginBottom: 10 }}>Add another department or factory area with its own entry points and rules.</div>
            <button className="btn s" disabled={!manage} onClick={() => setAdding(true)}><Plus size={14} /> Add module</button>
          </div>
        </div>
      </div>
      {adding && <ModuleForm onClose={() => setAdding(false)} onSaved={(m) => { setAdding(false); toast.ok(`Module “${m.name}” created.`); scope.reloadModules().then(() => setParams({ module: String(m.id) })); }} />}
    </>
  );
}
