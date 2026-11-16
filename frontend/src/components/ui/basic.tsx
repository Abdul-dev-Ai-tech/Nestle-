import { AlertTriangle, Check, ChevronLeft, ChevronRight, Loader2, Lock, Minus, Unlock, X, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { apiUrl } from '@/services/api';
import type { Camera, Door, EmployeeBrief, Violation } from '@/types';
import { avatarStyle, fmtNum, initials } from '@/utils/format';

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return <div className="loading"><Loader2 className="spin" size={26} /><span className="sm">{label}</span></div>;
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="banner err" role="alert">
      <AlertTriangle size={16} />
      <div className="grow">{message}</div>
      {onRetry && <button className="btn s" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Empty({ icon: Icon, title, children }: { icon?: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      {Icon && <div className="mut"><Icon size={28} /></div>}
      <b style={{ display: 'block', margin: '6px 0 2px', color: 'var(--ink2)' }}>{title}</b>
      {children && <div className="sm">{children}</div>}
    </div>
  );
}

export function SimTag({ label = 'Simulated' }: { label?: string }) {
  return <span className="chip warn">{label}</span>;
}

export function Avatar({ name, large, photoEmployeeId }: { name: string; large?: boolean; photoEmployeeId?: number }) {
  if (photoEmployeeId) {
    return <img className={large ? 'photo' : 'av'} style={large ? undefined : { objectFit: 'cover' }} alt={name}
      src={apiUrl(`/employees/${photoEmployeeId}/photo`)} />;
  }
  return <span className={`av ${large ? 'lg' : ''}`} style={avatarStyle(name)}>{initials(name)}</span>;
}

export function EmployeeCell({ employee }: { employee: EmployeeBrief | null }) {
  if (!employee) {
    return <div className="row ec"><span className="av">?</span><div><div className="b">Unidentified person</div><div className="xs mut">No badge / ID entered</div></div></div>;
  }
  return (
    <div className="row ec">
      <Avatar name={employee.full_name} photoEmployeeId={employee.has_photo ? employee.id : undefined} />
      <div><div className="b">{employee.full_name}</div><div className="xs mut">{employee.employee_code} · {employee.designation || '—'}</div></div>
    </div>
  );
}

export function ResultChip({ passed }: { passed: boolean }) {
  return passed
    ? <span className="chip ok"><Check size={12} /> PASS</span>
    : <span className="chip bad"><X size={12} /> FAIL</span>;
}

export function DecisionChip({ decision }: { decision: string }) {
  return decision === 'granted' ? <span className="chip ok">Access granted</span> : <span className="chip bad">Access denied</span>;
}

export function ModuleChip({ module }: { module: { name: string; color: string } | null }) {
  if (!module) return <span className="mut">—</span>;
  return <span className="chip"><span className="dot" style={{ background: module.color }} />{module.name}</span>;
}

export function MissingChips({ labels }: { labels: string[] }) {
  return <>{labels.map((l) => <span key={l} className="chip bad" style={{ marginRight: 4 }}>{l}</span>)}</>;
}

const VIO: Record<Violation['status'], [string, string]> = {
  open: ['bad', 'Open'], under_review: ['warn', 'Under review'], escalated: ['info', 'Escalated'], resolved: ['ok', 'Resolved'],
};
export const VIOLATION_STATUS = VIO;
export function ViolationChip({ status }: { status: Violation['status'] }) {
  return <span className={`chip ${VIO[status][0]}`}>{VIO[status][1]}</span>;
}

export function SeverityChip({ severity }: { severity: string }) {
  const cls = severity === 'critical' ? 'bad' : severity === 'high' ? 'warn' : 'info';
  return <span className={`chip ${cls}`}>{severity[0].toUpperCase() + severity.slice(1)}</span>;
}

export function SourceChip({ source }: { source: string }) {
  if (source === 'live') return null;
  return <span className="chip warn" title={source === 'sample' ? 'Seeded sample record' : 'Produced by the simulated detector'}>{source === 'sample' ? 'Sample' : 'Simulated'}</span>;
}

export function CameraStatusChip({ camera }: { camera: Camera }) {
  if (!camera.is_active) return <span className="chip"><span className="dot" />Disabled</span>;
  if (camera.type === 'browser') return <span className="chip info"><span className="dot" />Browser device</span>;
  const map = { online: ['ok', 'Online'], offline: ['bad', 'Offline'], unknown: ['', 'Not tested'] } as const;
  const [cls, label] = map[camera.status];
  return <span className={`chip ${cls}`}><span className="dot" />{label}</span>;
}

const DOOR: Record<Door['state'], [string, string, LucideIcon]> = {
  locked: ['', 'Locked', Lock], unlocked: ['ok', 'Unlocked', Unlock], held: ['warn', 'Held open', Unlock], fault: ['bad', 'Fault', AlertTriangle],
};
export const doorLabel = (d: Door) => DOOR[d.state][1];
export function DoorChip({ door }: { door: Door }) {
  const [cls, label, Icon] = DOOR[door.state];
  return <span className={`chip ${cls}`}><Icon size={12} /> {label}</span>;
}

export function DoorVisual({ door }: { door: Door | null }) {
  const open = door && (door.state === 'unlocked' || door.state === 'held');
  return <div className={`doorv ${open ? 'open' : ''} ${door?.state === 'fault' ? 'fault' : ''}`}><i /></div>;
}

const TONE: Record<string, string> = { ok: 't-ok', bad: 't-bad', gold: 't-gold', warn: 't-warn', info: 't-info', navy: 't-navy' };
export function Kpi({ icon: Icon, label, value, hint, tone, danger }: {
  icon: LucideIcon; label: string; value: ReactNode; hint?: ReactNode; tone?: keyof typeof TONE; danger?: boolean;
}) {
  return (
    <div className="card kpi">
      <div className="l"><span className={`ib ${tone ? TONE[tone] : ''}`}><Icon size={17} /></span>{label}</div>
      <div className={`v num ${danger ? 'dn' : ''}`}>{typeof value === 'number' ? fmtNum(value) : value}</div>
      {hint && <div className="d">{hint}</div>}
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="row sp" style={{ padding: '10px 16px', borderTop: '1px solid var(--line2)' }}>
      <span className="sm mut">{total ? (page - 1) * pageSize + 1 : 0}–{Math.min(total, page * pageSize)} of {fmtNum(total)}</span>
      <div className="row">
        <button className="btn s icn" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft size={14} /></button>
        <span className="sm">Page {page} / {pages}</span>
        <button className="btn s icn" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight size={14} /></button>
      </div>
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: [T, ReactNode][] }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(([v, label]) => (
        <button key={v} role="tab" aria-selected={v === value} className={v === value ? 'on' : ''} onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  );
}

export function Seg<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: [T, ReactNode][] }) {
  return (
    <div className="seg">
      {options.map(([v, label]) => <button key={v} className={v === value ? 'on' : ''} onClick={() => onChange(v)}>{label}</button>)}
    </div>
  );
}

export function Switch({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label?: string }) {
  return (
    <label className="sw">
      <input type="checkbox" checked={checked} disabled={disabled} aria-label={label} onChange={(e) => onChange(e.target.checked)} />
      <i />
    </label>
  );
}

export function Field({ label, children, error, hint }: { label: string; children: ReactNode; error?: string; hint?: string }) {
  return (
    <label className="fld">
      <span>{label}</span>
      {children}
      {error ? <span className="errt">{error}</span> : hint ? <span className="xs mut">{hint}</span> : null}
    </label>
  );
}

export function HBars({ rows }: { rows: { label: string; value: ReactNode; width: number; color?: string; dot?: string; title?: string }[] }) {
  if (!rows.length) return <Empty title="No data for this selection" />;
  return (
    <div>
      {rows.map((r) => (
        <div className="hb" key={r.label} title={r.title}>
          <span className="nw" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {r.dot && <span className="dot" style={{ background: r.dot, marginRight: 7 }} />}{r.label}
          </span>
          <div className="tr"><i style={{ width: `${Math.max(0, Math.min(100, r.width))}%`, background: r.color ?? '#1F4E85' }} /></div>
          <span className="b num">{r.value}</span>
        </div>
      ))}
    </div>
  );
}

export function PpeStateIcon({ state }: { state: 'ok' | 'bad' | 'na' }) {
  const Icon = state === 'ok' ? Check : state === 'bad' ? X : Minus;
  return <span className={`st ${state}`}><Icon size={16} /></span>;
}
