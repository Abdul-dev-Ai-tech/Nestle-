import { Check, Download, Info, Search, ShieldCheck, Users, X } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { C_BAD, ComplianceTrend, EntriesBars, ModuleLines } from '@/components/charts/Charts';
import { ErrorBanner, Field, HBars, Kpi, Pager, Seg, Spinner, Tabs } from '@/components/ui/basic';
import { EntriesTable } from '@/components/ui/EntriesTable';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { download } from '@/services/api';
import type { Entry, Page, SeriesPoint, Totals } from '@/types';
import { daysAgo, fmtDateTime, fmtNum, fmtPct, isoDate } from '@/utils/format';

type Tab = 'compliance' | 'shifts' | 'employees' | 'modules' | 'ppe' | 'repeat' | 'entries' | 'audit';
const ENDPOINT: Record<Tab, string> = { compliance: '/reports/compliance', shifts: '/reports/shifts', employees: '/reports/employees', modules: '/reports/modules', ppe: '/reports/ppe', repeat: '/reports/repeat-violations', entries: '/reports/entries', audit: '/reports/audit' };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Row = Record<string, any>;

function Table({ title, head, rows, cells }: { title: string; head: string[]; rows: Row[]; cells: (r: Row) => ReactNode[] }) {
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [rows]);
  const per = 12;
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <div className="ch" style={{ paddingBottom: 12 }}><div><h3>{title}</h3><p>{fmtNum(rows.length)} rows</p></div></div>
      <div className="tw"><table className="tbl">
        <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>
          {rows.slice((page - 1) * per, page * per).map((r, i) => <tr key={i}>{cells(r).map((c, j) => <td key={j} className={typeof c === 'number' ? 'num' : ''}>{typeof c === 'number' ? fmtNum(c) : c}</td>)}</tr>)}
          {!rows.length && <tr><td colSpan={head.length} className="empty">No data for this period.</td></tr>}
        </tbody>
      </table></div>
      <Pager page={page} pageSize={per} total={rows.length} onPage={setPage} />
    </div>
  );
}

export default function Reports() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>('compliance');
  const [from, setFrom] = useState(daysAgo(6));
  const [to, setTo] = useState(isoDate(new Date()));
  const [granularity, setGranularity] = useState<'day' | 'week' | 'month'>('day');
  const [page, setPage] = useState(1);
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  useEffect(() => { const t = setTimeout(() => { setSearch(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);
  useEffect(() => setPage(1), [tab, from, to, scope.moduleId, scope.factoryId]);
  const invalid = from > to;
  const base = { ...scope.params, date_from: from, date_to: to };
  const params = tab === 'compliance' ? { ...base, granularity } : tab === 'entries' ? { ...base, page, page_size: 12 } : tab === 'audit' ? { factory_id: scope.factoryId ?? undefined, date_from: from, date_to: to, q: search, page, page_size: 12 } : base;
  const tabs: [Tab, string][] = [['compliance', 'Compliance'], ['shifts', 'Shift report'], ['employees', 'Employee-wise'], ['modules', 'Module-wise'], ['ppe', 'PPE violations'], ['repeat', 'Repeat violations'], ['entries', 'Entry history']];
  if (can('audit.view')) tabs.push(['audit', 'Audit logs']);
  const report = useApi<Row>(scope.factoryId && !invalid ? ENDPOINT[tab] : null, params);
  const d = report.data;

  function preset(days: number) { setFrom(daysAgo(days)); setTo(isoDate(new Date())); }
  async function exportCsv() {
    try { await download(ENDPOINT[tab], { ...params, format: 'csv', page: undefined, page_size: undefined }, `${tab}_report.csv`); toast.ok('CSV exported.'); } catch (e) { toast.error(e); }
  }

  let body: ReactNode = null;
  if (d && tab === 'compliance') {
    const t = d.totals as Totals;
    const series = d.series as SeriesPoint[];
    body = (
      <>
        <div className="row wrap" style={{ marginBottom: 14 }}><Seg value={granularity} onChange={setGranularity} options={[['day', 'Daily'], ['week', 'Weekly'], ['month', 'Monthly']]} /><span className="sm mut">Grouping for the selected period</span></div>
        <div className="g g4">
          <Kpi icon={Users} label="Entries" value={t.entries} hint="In selected period" />
          <Kpi icon={Check} tone="ok" label="Successful" value={t.passed} hint="Access granted" />
          <Kpi icon={X} tone="bad" label="Failed" value={t.failed} hint="Access denied" />
          <Kpi icon={ShieldCheck} tone="gold" label="Compliance" value={fmtPct(t.compliance)} hint="Target 98%" />
        </div>
        <div className="g g2" style={{ marginTop: 16 }}>
          <div className="card"><div className="ch"><h3>Compliance rate</h3></div><div className="cb"><ComplianceTrend data={series} height={240} /></div></div>
          <div className="card"><div className="ch"><h3>Entries</h3></div><div className="cb"><EntriesBars data={series} height={240} /></div></div>
        </div>
        <Table title={`${{ day: 'Daily', week: 'Weekly', month: 'Monthly' }[granularity]} compliance report`} head={['Period', 'Entries', 'Successful', 'Failed', 'Compliance']}
          rows={[...series].reverse().filter((r) => r.entries > 0)} cells={(r) => [r.label, r.entries, r.passed, r.failed, fmtPct(r.compliance)]} />
      </>
    );
  }
  if (d && tab === 'shifts') body = <Table title="Shift report" head={['Shift', 'Hours', 'Entries', 'Successful', 'Failed', 'Compliance']} rows={d.rows} cells={(r) => [`Shift ${r.shift}`, r.hours || '—', r.entries, r.passed, r.failed, fmtPct(r.compliance)]} />;
  if (d && tab === 'employees') body = <Table title="Employee-wise compliance" head={['Employee ID', 'Employee', 'Department', 'Module', 'Entries', 'Violations', 'Compliance']} rows={d.rows} cells={(r) => [r.employee_code, r.full_name, r.department || '—', r.module || '—', r.entries, r.violations, fmtPct(r.compliance)]} />;
  if (d && tab === 'modules') body = (
    <>
      <div className="card"><div className="ch"><div><h3>Daily compliance by module</h3></div></div><div className="cb"><ModuleLines series={d.series} /></div></div>
      <Table title="Factory / module-wise report" head={['Module', 'Entry points', 'Entries', 'Successful', 'Failed', 'Compliance']} rows={d.rows} cells={(r) => [r.name, r.entry_points, r.entries, r.passed, r.failed, fmtPct(r.compliance)]} />
    </>
  );
  if (d && tab === 'ppe') {
    const max = Math.max(1, ...d.rows.map((r: Row) => r.missing));
    body = (
      <>
        <div className="card"><div className="ch"><div><h3>PPE violations by item</h3><p>Times each item was missing in the period</p></div></div>
          <div className="cb"><HBars rows={d.rows.map((r: Row) => ({ label: r.label, value: r.missing, width: (r.missing / max) * 100, color: C_BAD, title: `${r.missing} of ${r.checks} entries` }))} /></div></div>
        <Table title="PPE violation report" head={['PPE item', 'Entries where required', 'Missing', 'Miss rate']} rows={d.rows} cells={(r) => [r.label, r.checks, r.missing, r.miss_rate === null ? '—' : `${r.miss_rate}%`]} />
      </>
    );
  }
  if (d && tab === 'repeat') body = (
    <>
      <div className="note i"><Info size={16} /><div>Employees with <b>two or more</b> violations in the selected period. Use this list to plan refresher hygiene training.</div></div>
      <Table title="Repeat violations" head={['Employee ID', 'Employee', 'Module', 'Violations', 'Most missed item', 'Last violation']} rows={d.rows} cells={(r) => [r.employee_code, r.full_name, r.module || '—', r.violations, r.most_missed || '—', r.last_violation_at ? fmtDateTime(r.last_violation_at) : '—']} />
    </>
  );
  if (d && tab === 'entries') {
    const p = d as unknown as Page<Entry>;
    body = <div className="card"><div className="ch" style={{ paddingBottom: 12 }}><div><h3>Entry history</h3><p>{fmtNum(p.total)} entries</p></div></div><EntriesTable rows={p.items} full empty="No entries in this period." /><Pager page={page} pageSize={12} total={p.total} onPage={setPage} /></div>;
  }
  if (d && tab === 'audit') {
    const p = d as unknown as Page<Row>;
    body = (
      <div className="card">
        <div className="fbar" style={{ padding: '14px 16px 0' }}><div className="inw"><Search size={16} className="ic" /><input className="in" placeholder="Search user, action or detail" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search audit log" /></div><span className="sm mut">{fmtNum(p.total)} records</span></div>
        <div className="tw"><table className="tbl">
          <thead><tr><th>Date &amp; time</th><th>User</th><th>Action</th><th>Detail</th><th>IP address</th></tr></thead>
          <tbody>
            {p.items.map((a) => <tr key={a.id}><td className="nw num">{fmtDateTime(a.created_at)}</td><td>{a.user}</td><td><span className="chip">{a.action}</span></td><td>{a.detail}</td><td className="mut">{a.ip || '—'}</td></tr>)}
            {!p.items.length && <tr><td colSpan={5} className="empty">No audit records in this period.</td></tr>}
          </tbody>
        </table></div>
        <Pager page={page} pageSize={12} total={p.total} onPage={setPage} />
      </div>
    );
  }

  return (
    <>
      <PageHeader title="Reports & analytics" description={`${scope.modules.find((m) => m.id === scope.moduleId)?.name ?? 'All modules'} · figures are calculated from the entry records in the database.`}
        actions={<button className="btn pri" disabled={!can('reports.export') || invalid} title={can('reports.export') ? '' : 'Your role cannot export reports'} onClick={exportCsv}><Download size={16} /> Export CSV</button>} />
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="cb row wrap" style={{ alignItems: 'flex-end' }}>
          <Field label="From"><input type="date" className="in" style={{ width: 'auto' }} value={from} max={isoDate(new Date())} onChange={(e) => e.target.value && setFrom(e.target.value)} /></Field>
          <Field label="To"><input type="date" className="in" style={{ width: 'auto' }} value={to} max={isoDate(new Date())} onChange={(e) => e.target.value && setTo(e.target.value)} /></Field>
          <div className="fld"><span>Quick range</span><div className="row wrap">
            {[[0, 'Today'], [6, '7 days'], [29, '30 days'], [89, '90 days']].map(([n, l]) => <button key={l} className="btn s" onClick={() => preset(n as number)}>{l}</button>)}
          </div></div>
          {invalid && <span className="errt">“From” must be on or before “To”.</span>}
        </div>
      </div>
      <Tabs value={tab} onChange={setTab} tabs={tabs} />
      {report.error && <ErrorBanner message={report.error} onRetry={report.reload} />}
      {report.loading && !d ? <Spinner /> : body}
    </>
  );
}
