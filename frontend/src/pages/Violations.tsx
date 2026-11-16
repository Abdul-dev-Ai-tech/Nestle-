import { AlertTriangle, Bell, Camera as CameraIcon, Check, Clock, DoorOpen, Download, ImageOff, KeyRound, Search, ShieldAlert, Users } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { EmployeeCell, Empty, ErrorBanner, Kpi, MissingChips, ModuleChip, Pager, Seg, SeverityChip, SourceChip, Spinner, Tabs, ViolationChip } from '@/components/ui/basic';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { ViolationModal } from '@/features/violations/ViolationModal';
import { useApi } from '@/hooks/useApi';
import { apiUrl, download, post } from '@/services/api';
import type { Alert, Page, Violation } from '@/types';
import { PPE_ITEMS, PPE_LABELS } from '@/types';
import { ago, daysAgo, fmtDateTime, isoDate, titleCase } from '@/utils/format';

type VList = Page<Violation> & { counts: Record<Violation['status'], number> };
type AList = Page<Alert> & { unread: number; unacknowledged: number };
const RANGES: Record<string, () => string | undefined> = { today: () => isoDate(new Date()), '7': () => daysAgo(6), '30': () => daysAgo(29), all: () => undefined };

function ViolationsTab({ onOpen, refreshKey }: { onOpen: (id: number) => void; refreshKey: number }) {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [item, setItem] = useState('all');
  const [severity, setSeverity] = useState('all');
  const [range, setRange] = useState('7');
  const [page, setPage] = useState(1);
  useEffect(() => { const t = setTimeout(() => { setSearch(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);
  useEffect(() => setPage(1), [status, item, severity, range, scope.moduleId, scope.factoryId]);
  const filters = { ...scope.params, q: search, status, item, severity, date_from: RANGES[range]() };
  const list = useApi<VList>(scope.factoryId ? '/violations' : null, { ...filters, page, page_size: 8, _r: refreshKey }, 15000);
  const c = list.data?.counts;

  return (
    <>
      {list.error && <ErrorBanner message={list.error} onRetry={list.reload} />}
      <div className="g g4">
        <Kpi icon={AlertTriangle} tone="bad" label="Open" value={c?.open ?? 0} danger={!!c?.open} hint="Awaiting review" />
        <Kpi icon={Clock} tone="warn" label="Under review" value={c?.under_review ?? 0} hint="Being investigated" />
        <Kpi icon={ShieldAlert} tone="info" label="Escalated" value={c?.escalated ?? 0} hint="Sent to management" />
        <Kpi icon={Check} tone="ok" label="Resolved" value={c?.resolved ?? 0} hint="Closed with action" />
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <div className="fbar" style={{ padding: '14px 16px 0' }}>
          <div className="inw"><Search size={16} className="ic" /><input className="in" placeholder="Search employee name or ID" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search violations" /></div>
          <select className="in" value={item} onChange={(e) => setItem(e.target.value)} aria-label="PPE type"><option value="all">All PPE types</option>{PPE_ITEMS.map((i) => <option key={i} value={i}>Missing {PPE_LABELS[i]}</option>)}</select>
          <select className="in" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status"><option value="all">All statuses</option><option value="open">Open</option><option value="under_review">Under review</option><option value="escalated">Escalated</option><option value="resolved">Resolved</option></select>
          <select className="in" value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label="Severity"><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option></select>
          <select className="in" value={range} onChange={(e) => setRange(e.target.value)} aria-label="Date range"><option value="today">Today</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option><option value="all">All time</option></select>
          <div className="grow" />
          {can('reports.export') && <button className="btn s" onClick={() => download('/reports/entries', { ...scope.params, format: 'csv', result: 'denied', date_from: RANGES[range]() }, 'violations.csv').catch(toast.error)}><Download size={14} /> Export CSV</button>}
        </div>
        {!list.data ? <Spinner /> : (
          <>
            <div className="tw"><table className="tbl">
              <thead><tr><th>Evidence</th><th>Employee</th><th>Missing PPE</th><th>Date &amp; time</th><th>Camera / entry point</th><th>Module</th><th>Severity</th><th>Status</th></tr></thead>
              <tbody>
                {list.data.items.map((v) => (
                  <tr key={v.id} className="clk" onClick={() => onOpen(v.id)}>
                    <td>{v.has_evidence ? <img className="evt" style={{ objectFit: 'cover' }} src={apiUrl(`/entries/${v.entry_id}/evidence`)} alt="Evidence thumbnail" loading="lazy" />
                      : <span className="evt" style={{ display: 'grid', placeItems: 'center', color: '#8B7E71' }} title="No evidence image stored"><ImageOff size={16} /></span>}</td>
                    <td><EmployeeCell employee={v.employee} /></td>
                    <td><div className="xs mut" style={{ marginBottom: 3 }}>#{v.id} · PPE non-compliance <SourceChip source={v.source} /></div><MissingChips labels={v.missing_labels} /></td>
                    <td className="nw num">{fmtDateTime(v.created_at)}</td>
                    <td>{v.camera ?? '—'}<div className="xs mut">{v.entry_point ?? '—'}</div></td>
                    <td><ModuleChip module={v.module} /></td>
                    <td><SeverityChip severity={v.severity} /></td><td><ViolationChip status={v.status} /></td>
                  </tr>
                ))}
                {!list.data.items.length && <tr><td colSpan={8} className="empty">No violations match these filters.</td></tr>}
              </tbody>
            </table></div>
            <Pager page={page} pageSize={8} total={list.data.total} onPage={setPage} />
          </>
        )}
      </div>
    </>
  );
}

const ALERT_ICON: Record<string, typeof Bell> = { ppe_violation: AlertTriangle, repeat_violation: Users, door_fault: DoorOpen, camera_offline: CameraIcon, manual_override: KeyRound };

function AlertsTab({ onOpen }: { onOpen: (id: number) => void }) {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const [filter, setFilter] = useState<'all' | 'unread' | 'open' | 'critical'>('all');
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [filter, scope.factoryId]);
  const list = useApi<AList>(scope.factoryId ? '/alerts' : null, { factory_id: scope.factoryId ?? undefined, filter, page, page_size: 12 }, 10000);

  async function ack(a: Alert) { try { await post(`/alerts/${a.id}/acknowledge`); list.reload(); } catch (e) { toast.error(e); } }
  async function readAll() { try { await post('/alerts/read-all', undefined, { factory_id: scope.factoryId ?? undefined }); toast.ok('All alerts marked as read.'); list.reload(); } catch (e) { toast.error(e); } }

  return (
    <>
      <div className="row sp wrap" style={{ marginBottom: 16 }}>
        <Seg value={filter} onChange={setFilter} options={[['all', 'All'], ['unread', 'Unread'], ['open', 'Unacknowledged'], ['critical', 'Critical']]} />
        <div className="row"><span className="sm mut">{list.data?.unread ?? 0} unread · {list.data?.unacknowledged ?? 0} unacknowledged</span>
          <button className="btn" onClick={readAll}><Check size={15} /> Mark all read</button></div>
      </div>
      {list.error && <ErrorBanner message={list.error} onRetry={list.reload} />}
      {!list.data ? <Spinner /> : (
        <div className="col">
          {list.data.items.map((a) => {
            const Icon = ALERT_ICON[a.type] ?? Bell;
            return (
              <div key={a.id} className="card" style={a.read ? undefined : { borderLeft: `4px solid ${a.severity === 'critical' ? 'var(--fail)' : a.severity === 'high' ? 'var(--warn)' : 'var(--info)'}` }}>
                <div className="cb row wrap" style={{ alignItems: 'flex-start' }}>
                  <span className={`ib ${a.severity === 'critical' ? 't-bad' : a.severity === 'high' ? 't-warn' : 't-info'}`} style={{ width: 38, height: 38 }}><Icon size={18} /></span>
                  <div className="grow" style={{ minWidth: 200 }}>
                    <div className="row wrap" style={{ gap: 6 }}><SeverityChip severity={a.severity} /><span className="chip">{titleCase(a.type)}</span>{a.acknowledged && <span className="chip ok">Acknowledged</span>}{!a.read && <span className="chip info">New</span>}</div>
                    <div className="b" style={{ marginTop: 6 }}>{a.title}</div><div className="sm mut">{a.detail}</div>
                    <div className="xs mut" style={{ marginTop: 4 }}>{fmtDateTime(a.created_at)} · {ago(a.created_at)}</div>
                  </div>
                  <div className="row">
                    {a.ref_type === 'violation' && a.ref_id && <button className="btn s" onClick={() => onOpen(a.ref_id!)}>View violation</button>}
                    {!a.acknowledged && <button className="btn s pri" disabled={!can('alerts.manage')} onClick={() => ack(a)}>Acknowledge</button>}
                  </div>
                </div>
              </div>
            );
          })}
          {!list.data.items.length && <div className="card"><Empty icon={Check} title="No alerts in this view" /></div>}
          {list.data.total > 12 && <div className="card"><Pager page={page} pageSize={12} total={list.data.total} onPage={setPage} /></div>}
        </div>
      )}
    </>
  );
}

export default function Violations() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'alerts' && can('alerts.view') ? 'alerts' : 'violations';
  const [open, setOpen] = useState<number | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <>
      <PageHeader title="Violations & alerts" description="Every failed PPE check with evidence and review status, plus system notifications."
        actions={can('alerts.view') && <button className="btn pri" onClick={() => setParams(tab === 'violations' ? { tab: 'alerts' } : {})}>
          {tab === 'violations' ? <><Bell size={16} /> Open alert center</> : <><AlertTriangle size={16} /> Review violations</>}</button>} />
      <Tabs value={tab} onChange={(t) => setParams(t === 'alerts' ? { tab: 'alerts' } : {})}
        tabs={can('alerts.view') ? [['violations', 'Violations'], ['alerts', 'Alert center']] : [['violations', 'Violations']]} />
      {tab === 'violations' ? <ViolationsTab onOpen={setOpen} refreshKey={refreshKey} /> : <AlertsTab onOpen={setOpen} />}
      {open && <ViolationModal id={open} onClose={() => setOpen(null)} onChanged={() => setRefreshKey((k) => k + 1)} />}
    </>
  );
}
