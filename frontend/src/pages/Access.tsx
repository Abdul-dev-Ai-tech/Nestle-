import { AlertTriangle, DoorOpen, Download, KeyRound, Lock, Search, Unlock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { DoorChip, DoorVisual, ErrorBanner, Field, Kpi, ModuleChip, Pager, Seg, SimTag, Spinner, Tabs } from '@/components/ui/basic';
import { EntriesTable } from '@/components/ui/EntriesTable';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { download, post } from '@/services/api';
import type { AccessEvent, DashboardSummary, Door, Entry, Page } from '@/types';
import { fmtDateTime, isoDate, titleCase } from '@/utils/format';

const REASONS = ['Maintenance access', 'Emergency / evacuation', 'Visitor escort', 'Material movement', 'Sensor or camera fault', 'Other'];

function Override({ door, command, onClose, onDone }: { door: Door; command: 'unlock' | 'hold'; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [reason, setReason] = useState(REASONS[0]);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  async function confirm() {
    if (reason === 'Other' && note.trim().length < 5) return setError('Please describe the reason (at least 5 characters).');
    try {
      await post(`/access/doors/${door.id}/command`, { command, reason: note.trim() ? `${reason} — ${note.trim()}` : reason });
      toast.ok(`${door.name}: ${command === 'hold' ? 'held open' : 'unlocked'}${door.hardware_active ? '' : ' (simulated)'}.`);
      onDone();
    } catch (e) { setError((e as Error).message); }
  }
  return (
    <Modal title={`Manual override — ${door.name}`} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn dan" onClick={confirm}>{command === 'hold' ? 'Hold door open' : 'Unlock door'}</button></>}>
      <div className="note" style={{ marginBottom: 14 }}><AlertTriangle size={16} /><div>
        You are about to {command === 'hold' ? <b>hold this door open</b> : <b>unlock this door for {door.unlock_seconds} seconds</b>} without a PPE check.
        This is recorded in the audit log under your name. {door.hardware_active ? 'This door is connected to real hardware.' : 'This door is in simulation mode — no physical door will move.'}
      </div></div>
      <div className="col">
        <Field label="Reason"><select className="in" value={reason} onChange={(e) => setReason(e.target.value)}>{REASONS.map((r) => <option key={r}>{r}</option>)}</select></Field>
        <Field label="Note (required for “Other”)"><textarea className="in" rows={2} maxLength={200} placeholder="Add context for the audit trail" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        {error && <span className="errt" role="alert">{error}</span>}
      </div>
    </Modal>
  );
}

export default function Access() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const allow = can('access.override');
  const [tab, setTab] = useState<'history' | 'events'>('history');
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  const [result, setResult] = useState<'all' | 'granted' | 'denied'>('all');
  const [page, setPage] = useState(1);
  const [evPage, setEvPage] = useState(1);
  const [override, setOverride] = useState<{ door: Door; command: 'unlock' | 'hold' } | null>(null);
  useEffect(() => { const t = setTimeout(() => { setSearch(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);
  useEffect(() => { setPage(1); setEvPage(1); }, [result, scope.moduleId, scope.factoryId]);

  const doors = useApi<Door[]>(scope.factoryId ? '/access/doors' : null, scope.params, 4000);
  const summary = useApi<DashboardSummary>(scope.factoryId ? '/dashboard/summary' : null, scope.params, 15000);
  const today = isoDate(new Date());
  const overrides = useApi<Page<AccessEvent>>(scope.factoryId ? '/access/events' : null, { ...scope.params, manual_only: true, page_size: 100 }, 15000);
  const entries = useApi<Page<Entry>>(tab === 'history' && scope.factoryId ? '/access/entries' : null, { ...scope.params, q: search, result, page, page_size: 12 }, 10000);
  const events = useApi<Page<AccessEvent>>(tab === 'events' && scope.factoryId ? '/access/events' : null, { ...scope.params, page: evPage, page_size: 15 }, 10000);
  const list = doors.data ?? [];
  const overridesToday = (overrides.data?.items ?? []).filter((e) => e.occurred_at.slice(0, 10) >= today && /unlock|hold_open/.test(e.type)).length;

  async function lock(door: Door) {
    try { await post(`/access/doors/${door.id}/command`, { command: door.state === 'held' ? 'release' : 'lock', reason: 'Operator action' }); toast.ok(`${door.name} locked.`); doors.reload(); } catch (e) { toast.error(e); }
  }
  const moduleOf = (id: number) => scope.modules.find((m) => m.id === id) ?? null;

  return (
    <>
      <PageHeader title="Smart access control" description="Doors open automatically on a PASS result. Manual overrides need a reason and are logged."
        actions={summary.data?.door_mode === 'simulation' ? <SimTag label="Door simulation mode" /> : <span className="chip info">Hardware mode enabled</span>} />
      {doors.error && <ErrorBanner message={doors.error} onRetry={doors.reload} />}
      <div className="g g4">
        <Kpi icon={Unlock} tone="ok" label="Access granted today" value={summary.data?.today.passed ?? 0} hint="Automatic release on PASS" />
        <Kpi icon={Lock} tone="bad" label="Access denied today" value={summary.data?.today.failed ?? 0} hint="Door kept locked on FAIL" />
        <Kpi icon={KeyRound} tone="warn" label="Manual overrides today" value={overridesToday} hint="Authorized users only" />
        <Kpi icon={DoorOpen} tone="info" label="Door controllers online" value={`${list.filter((d) => d.online).length} / ${list.length}`} hint={list.some((d) => !d.online) ? <span className="dn b">Attention needed</span> : 'All healthy'} />
      </div>
      {!allow && <div className="note" style={{ marginTop: 16 }}><Lock size={16} /><div>Your role can view door status but cannot lock, unlock or override doors.</div></div>}
      {!doors.data ? <Spinner /> : (
        <div className="g g4" style={{ marginTop: 16 }}>
          {list.map((d) => (
            <div className="card lift" key={d.id}><div className="cb">
              <div className="row"><DoorVisual door={d} />
                <div className="grow"><div className="b">{d.name}</div><div className="xs mut" style={{ margin: '3px 0 6px' }}><ModuleChip module={moduleOf(d.module_id)} /></div><DoorChip door={d} /></div></div>
              <div className="xs mut" style={{ margin: '10px 0' }}>
                {d.state === 'fault' ? 'Controller not responding — held locked (fail-secure).' : `${d.hardware_active ? 'Hardware' : 'Simulated'} controller · unlock ${d.unlock_seconds}s · auto-open ${d.auto_open ? 'on' : 'off'}`}
              </div>
              <div className="row wrap" style={{ gap: 6 }}>
                {d.state === 'locked' || d.state === 'fault' ? (
                  <>
                    <button className="btn s" disabled={!allow || d.state === 'fault'} onClick={() => setOverride({ door: d, command: 'unlock' })}><Unlock size={13} /> Unlock</button>
                    <button className="btn s" disabled={!allow || d.state === 'fault'} onClick={() => setOverride({ door: d, command: 'hold' })}>Hold open</button>
                  </>
                ) : <button className="btn s pri" disabled={!allow} onClick={() => lock(d)}><Lock size={13} /> Lock now</button>}
              </div>
            </div></div>
          ))}
          {!list.length && <div className="card empty" style={{ gridColumn: '1/-1' }}>No doors configured for this selection.</div>}
        </div>
      )}
      <div className="card" style={{ marginTop: 16 }}>
        <div style={{ padding: '6px 16px 0' }}><Tabs value={tab} onChange={setTab} tabs={[['history', 'Entry history'], ['events', 'Access event log']]} /></div>
        {tab === 'history' ? (
          <>
            <div className="fbar" style={{ padding: '0 16px' }}>
              <div className="inw"><Search size={16} className="ic" /><input className="in" placeholder="Search employee name or ID" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search entries" /></div>
              <Seg value={result} onChange={setResult} options={[['all', 'All'], ['granted', 'Granted'], ['denied', 'Denied']]} />
              <div className="grow" />
              {can('reports.export') && <button className="btn s" onClick={() => download('/reports/entries', { ...scope.params, format: 'csv', result }, 'entry_history.csv').catch(toast.error)}><Download size={14} /> Export CSV</button>}
            </div>
            {!entries.data ? <Spinner /> : <><EntriesTable rows={entries.data.items} full empty="No matching entries." /><Pager page={page} pageSize={12} total={entries.data.total} onPage={setPage} /></>}
          </>
        ) : !events.data ? <Spinner /> : (
          <>
            <div className="tw"><table className="tbl">
              <thead><tr><th>Time</th><th>Door</th><th>Event</th><th>By</th><th>Reason</th></tr></thead>
              <tbody>
                {events.data.items.map((e) => (
                  <tr key={e.id}><td className="nw num">{fmtDateTime(e.occurred_at)}</td><td>{e.door}</td>
                    <td><span className={`chip ${/fault|blocked/.test(e.type) ? 'bad' : /manual|hold/.test(e.type) ? 'warn' : e.type === 'auto_unlock' ? 'ok' : ''}`}>{titleCase(e.type)}</span>{e.simulated && <span className="chip" style={{ marginLeft: 6 }}>Simulated</span>}</td>
                    <td>{e.actor}</td><td className="mut">{e.reason}</td></tr>
                ))}
                {!events.data.items.length && <tr><td colSpan={5} className="empty">No access events yet.</td></tr>}
              </tbody>
            </table></div>
            <Pager page={evPage} pageSize={15} total={events.data.total} onPage={setEvPage} />
          </>
        )}
      </div>
      {override && <Override {...override} onClose={() => setOverride(null)} onDone={() => { setOverride(null); doors.reload(); overrides.reload(); }} />}
    </>
  );
}
