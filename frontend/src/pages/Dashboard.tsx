import { AlertTriangle, Camera as CameraIcon, Check, Clock, DoorOpen, Factory, KeyRound, ShieldCheck, Users, X } from 'lucide-react';
import { useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { ComplianceTrend, EntriesBars, C_BAD } from '@/components/charts/Charts';
import { CameraStatusChip, DoorChip, Empty, ErrorBanner, HBars, Kpi, Seg, Spinner } from '@/components/ui/basic';
import { EntriesTable } from '@/components/ui/EntriesTable';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useApi } from '@/hooks/useApi';
import { useClock } from '@/hooks/useClock';
import type { DashboardSummary, Totals } from '@/types';
import { ago, fmtNum, fmtPct } from '@/utils/format';

function Delta({ now, before, invert, points }: { now: number | null; before: number | null; invert?: boolean; points?: boolean }) {
  if (now === null || before === null || (!points && !before)) return <>vs same time yesterday</>;
  const d = points ? now - before : ((now - before) / before) * 100;
  const good = invert ? d <= 0 : d >= 0;
  return <><span className={`${good ? 'up' : 'dn'} b`}>{d >= 0 ? '▲' : '▼'} {Math.abs(d).toFixed(1)}{points ? ' pts' : '%'}</span> vs yesterday</>;
}

function Welcome({ data, today }: { data: DashboardSummary; today: Totals }) {
  const { me, can } = useAuth();
  const scope = useScope();
  const now = useClock();
  const hour = now.getHours();
  const moduleName = scope.modules.find((m) => m.id === scope.moduleId)?.name ?? 'All modules';
  const rate = today.compliance;
  const spot = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`);
  };
  return (
    <div className="welcome" onMouseMove={spot}>
      <span className="spot" />
      <div className="grow" style={{ minWidth: 260 }}>
        <h1>{hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'}, {me?.user.full_name.split(' ')[0]}</h1>
        <p>
          {today.entries
            ? <><b>{fmtNum(today.entries)}</b> people have entered today with <b>{fmtPct(rate)}</b> PPE compliance. </>
            : 'No entries recorded yet today. '}
          {data.open_violations
            ? <><b>{data.open_violations}</b> violation{data.open_violations > 1 ? 's' : ''} still need{data.open_violations > 1 ? '' : 's'} review.</>
            : 'No violations waiting for review.'}
        </p>
        <div className="meta">
          <span><Clock size={13} />{now.toLocaleDateString([], { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })} · {now.toLocaleTimeString()}</span>
          <span><Factory size={13} />{data.factory.name} · {moduleName}</span>
          <span><span className="dot pulse" style={{ color: '#6BE3A6' }} />Live data · updates every 10 s</span>
        </div>
        <div className="row wrap" style={{ marginTop: 20 }}>
          {can('monitoring.view') && <Link className="btn gold lg" to="/monitoring"><CameraIcon size={17} /> Open live monitoring</Link>}
          {data.open_violations > 0 && can('violations.view') && (
            <Link className="btn lg" style={{ background: 'rgba(255,255,255,.1)', borderColor: 'rgba(255,255,255,.22)', color: '#fff' }} to="/violations"><AlertTriangle size={16} /> Review violations</Link>
          )}
        </div>
      </div>
      <div className="gauge" title="PPE compliance today">
        <svg width="100%" height="100%" viewBox="0 0 120 120">
          <defs><linearGradient id="gg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#F3E2C3" /><stop offset="1" stopColor="#B8894A" /></linearGradient></defs>
          <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,.12)" strokeWidth="10" />
          <circle className="gp" cx="60" cy="60" r="50" fill="none" stroke="url(#gg)" strokeWidth="10" strokeLinecap="round" pathLength={100}
            style={{ ['--p' as string]: rate === null ? 0 : Math.round(rate) }} />
        </svg>
        <div><b>{fmtPct(rate)}</b><small>Compliance<br />today</small></div>
      </div>
    </div>
  );
}

type ChartKey = 'trend' | 'daily' | 'module' | 'ppe';
const CHART_TEXT: Record<ChartKey, string> = {
  trend: 'Share of entries that passed the PPE check — last 30 days',
  daily: 'Successful and failed entries — last 14 days',
  module: 'Compliance by factory module — last 7 days (scale starts at 80%)',
  ppe: 'How often each PPE item was missing — last 7 days',
};

export default function Dashboard() {
  const scope = useScope();
  const { can } = useAuth();
  const [chart, setChart] = useState<ChartKey>('trend');
  const { data, loading, error, reload } = useApi<DashboardSummary>(scope.factoryId ? '/dashboard/summary' : null, scope.params, 10000);

  if (loading && !data) return <><PageHeader title="Overview dashboard" /><Spinner label="Loading today's figures…" /></>;
  if (error || !data) return <><PageHeader title="Overview dashboard" /><ErrorBanner message={error ?? 'No data'} onRetry={reload} /></>;

  const { today, yesterday_same_time: yd } = data;
  const sample = data.data_sources.sample ?? 0;
  const simulated = data.data_sources.simulation ?? 0;
  const maxMissing = Math.max(1, ...data.missing_ppe.map((m) => m.missing));
  const entryPoints = scope.modules.filter((m) => m.is_active && (!scope.moduleId || m.id === scope.moduleId))
    .flatMap((m) => m.entry_points.map((e) => ({ e, m })));

  return (
    <>
      <PageHeader title="Overview dashboard" description="Live entry compliance for the selected factory and module." />
      {(sample > 0 || simulated > 0 || data.ai_mode === 'simulation') && (
        <div className="banner sim">
          <AlertTriangle size={16} />
          <div>
            {data.ai_mode === 'simulation' && <><b>AI simulation mode.</b> New checks use a simulated detector, not a trained model. </>}
            {sample > 0 && <>The last 30 days include <b>{fmtNum(sample)}</b> seeded sample entries. </>}
            {simulated > 0 && <><b>{fmtNum(simulated)}</b> entries came from simulated checks. </>}
            Figures are read from the database; remove sample data before real use (see docs/INSTALLATION.md).
          </div>
        </div>
      )}
      <Welcome data={data} today={today} />
      <div className="g g5">
        <Kpi icon={Users} label="Total personnel entries" value={today.entries} hint={<Delta now={today.entries} before={yd.entries} />} />
        <Kpi icon={ShieldCheck} tone="gold" label="Compliance rate" value={fmtPct(today.compliance)} hint={<Delta now={today.compliance} before={yd.compliance} points />} />
        <Kpi icon={Check} tone="ok" label="Successful entries" value={today.passed} hint={<Delta now={today.passed} before={yd.passed} />} />
        <Kpi icon={X} tone="bad" label="Failed entries" value={today.failed} danger={today.failed > 0} hint={<Delta now={today.failed} before={yd.failed} invert />} />
        <Kpi icon={AlertTriangle} tone="bad" label="Active violations" value={data.open_violations} danger={data.open_violations > 0} hint={<>Open, awaiting review · <b>{today.failed}</b> today</>} />
      </div>

      <div className="g g21" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="ch">
            <div><h3>Compliance analytics</h3><p>{CHART_TEXT[chart]}</p></div>
            <Seg value={chart} onChange={setChart} options={[['trend', 'Trend'], ['daily', 'Daily entries'], ['module', 'By module'], ['ppe', 'Missing PPE']]} />
          </div>
          <div className="cb">
            {chart === 'trend' && <ComplianceTrend data={data.daily} />}
            {chart === 'daily' && <EntriesBars data={data.daily.slice(-14)} />}
            {chart === 'module' && <div style={{ padding: '14px 0' }}><HBars rows={data.by_module.map((m) => ({ label: m.name, dot: m.color, color: m.color, value: fmtPct(m.compliance), width: m.compliance === null ? 0 : (m.compliance - 80) * 5, title: `${m.entries} entries · ${m.failed} failed` }))} /></div>}
            {chart === 'ppe' && <div style={{ padding: '14px 0' }}><HBars rows={data.missing_ppe.map((m) => ({ label: m.label, value: m.missing, width: (m.missing / maxMissing) * 100, color: C_BAD }))} /></div>}
          </div>
        </div>
        <div className="card">
          <div className="ch">
            <div><h3>Active alerts</h3><p>{data.alerts.unacknowledged} unacknowledged · {data.alerts.critical} critical</p></div>
            {can('alerts.view') && <Link className="btn s" to="/violations?tab=alerts">Alert center</Link>}
          </div>
          <div className="cb col" style={{ gap: 8 }}>
            {data.alerts.items.map((a) => {
              const Icon = a.type.includes('door') ? DoorOpen : a.type.includes('camera') ? CameraIcon : a.type.includes('override') ? KeyRound : AlertTriangle;
              return (
                <Link key={a.id} to="/violations?tab=alerts" className="li" style={{ alignItems: 'flex-start', textDecoration: 'none', color: 'inherit' }}>
                  <span className={`ib ${a.severity === 'critical' ? 't-bad' : a.severity === 'high' ? 't-warn' : 't-info'}`} style={{ width: 30, height: 30 }}><Icon size={15} /></span>
                  <div className="grow"><div className="b" style={{ lineHeight: 1.3 }}>{a.title}</div><div className="xs mut">{a.severity} · {ago(a.created_at)}</div></div>
                </Link>
              );
            })}
            {!data.alerts.items.length && <Empty icon={Check} title="All clear">No active alerts.</Empty>}
          </div>
        </div>
      </div>

      <div className="g g21" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="ch" style={{ paddingBottom: 14 }}>
            <div><h3>Recent entry activity</h3><p>Latest PPE checks across entry points</p></div>
            {can('access.view') && <Link className="btn s" to="/access">Full history</Link>}
          </div>
          <EntriesTable rows={data.recent_entries} empty="No entries recorded yet." />
        </div>
        <div className="card">
          <div className="ch" style={{ paddingBottom: 14 }}>
            <div><h3>Live camera &amp; door status</h3>
              <p>{data.cameras.filter((c) => c.status === 'online').length} of {data.cameras.length} cameras online · {data.doors.filter((d) => d.online).length} of {data.doors.length} doors online</p></div>
          </div>
          <div className="tw">
            <table className="tbl">
              <thead><tr><th>Entry point</th><th>Camera</th><th>Door access</th></tr></thead>
              <tbody>
                {entryPoints.map(({ e, m }) => {
                  const cam = data.cameras.find((c) => c.entry_point_id === e.id);
                  const door = data.doors.find((d) => d.entry_point_id === e.id);
                  return (
                    <tr key={e.id}>
                      <td title={m.name}><span className="dot" style={{ background: m.color, marginRight: 8 }} /><b>{e.name}</b></td>
                      <td>{cam ? <CameraStatusChip camera={cam} /> : <span className="mut sm">No camera</span>}</td>
                      <td>{door ? <DoorChip door={door} /> : <span className="mut sm">No door</span>}</td>
                    </tr>
                  );
                })}
                {!entryPoints.length && <tr><td colSpan={3} className="empty">No entry points configured.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="row" style={{ padding: '12px 16px', borderTop: '1px solid var(--line2)' }}>
            {can('cameras.view') && <Link className="btn s" to="/cameras"><CameraIcon size={14} /> Cameras</Link>}
            {can('access.view') && <Link className="btn s" to="/access"><DoorOpen size={14} /> Doors</Link>}
          </div>
        </div>
      </div>
    </>
  );
}
