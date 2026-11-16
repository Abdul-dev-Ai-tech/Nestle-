import { AlertTriangle, Pencil, ShieldCheck, Upload, Users } from 'lucide-react';
import { useRef, useState } from 'react';
import { Avatar, Kpi, MissingChips, ModuleChip, Pager, ResultChip, SeverityChip, SourceChip, Spinner, Tabs, ViolationChip } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { postForm } from '@/services/api';
import type { Employee, Entry, Page, Violation } from '@/types';
import { fmtDateTime, fmtPct } from '@/utils/format';

export function EmployeeProfile({ id, onClose, onEdit, onChanged }: { id: number; onClose: () => void; onEdit: (e: Employee) => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<'entries' | 'violations'>('entries');
  const [page, setPage] = useState(1);
  const [photoKey, setPhotoKey] = useState(0);
  const file = useRef<HTMLInputElement>(null);
  const emp = useApi<Employee>(`/employees/${id}`);
  const entries = useApi<Page<Entry>>(`/employees/${id}/entries`, { page, page_size: 8 });
  const violations = useApi<Violation[]>(tab === 'violations' ? `/employees/${id}/violations` : null);
  const e = emp.data;

  async function upload(f: File | undefined) {
    if (!f) return;
    const form = new FormData();
    form.set('file', f);
    try {
      await postForm(`/employees/${id}/photo`, form);
      toast.ok('Profile image updated.');
      setPhotoKey((k) => k + 1);
      emp.reload();
      onChanged();
    } catch (err) {
      toast.error(err);
    }
  }

  return (
    <Modal title="Employee profile" wide onClose={onClose}
      footer={<>{can('employees.manage') && e && <button className="btn" onClick={() => onEdit(e)}><Pencil size={15} /> Edit</button>}<button className="btn pri" onClick={onClose}>Close</button></>}>
      {!e ? <Spinner /> : (
        <>
          <div className="row wrap" style={{ marginBottom: 14 }}>
            <span key={photoKey}><Avatar name={e.full_name} large photoEmployeeId={e.has_photo ? e.id : undefined} /></span>
            <div className="grow">
              <div className="b" style={{ fontSize: 17 }}>{e.full_name}</div>
              <div className="sm mut">{e.employee_code} · {e.designation || '—'} · {e.department ?? 'No department'}</div>
              <div className="row wrap" style={{ marginTop: 6, gap: 6 }}>
                <ModuleChip module={e.module} /><span className="chip">Shift {e.shift}</span>
                {e.status === 'active' ? <span className="chip ok">Active</span> : <span className="chip">Inactive</span>}
                <span className="chip">{e.beard_net_applicable ? 'Beard net applies' : 'Beard net not applicable'}</span>
              </div>
            </div>
            {can('employees.manage') && (
              <>
                <input ref={file} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(ev) => { upload(ev.target.files?.[0]); ev.target.value = ''; }} />
                <button className="btn s" onClick={() => file.current?.click()}><Upload size={14} /> {e.has_photo ? 'Replace photo' : 'Upload photo'}</button>
              </>
            )}
          </div>
          <div className="g g3" style={{ marginBottom: 14 }}>
            <Kpi icon={Users} label="Entries (30 days)" value={e.stats_30d?.entries ?? 0} hint={`Last: ${e.stats_all?.last_entry_at ? fmtDateTime(e.stats_all.last_entry_at) : '—'}`} />
            <Kpi icon={ShieldCheck} tone="gold" label="Compliance (30 days)" value={fmtPct(e.stats_30d?.compliance)} hint="Passed checks" />
            <Kpi icon={AlertTriangle} tone="bad" label="Violations (all time)" value={e.stats_all?.violations ?? 0} danger={(e.stats_all?.violations ?? 0) >= 3} hint={(e.stats_30d?.violations ?? 0) + ' in the last 30 days'} />
          </div>
          <Tabs value={tab} onChange={setTab} tabs={[['entries', 'Entry history'], ['violations', 'Violation history']]} />
          {tab === 'entries' ? (
            <div style={{ border: '1px solid var(--line)', borderRadius: 12 }}>
              <div className="tw"><table className="tbl">
                <thead><tr><th>Time</th><th>Entry point</th><th>Result</th><th>Missing PPE</th></tr></thead>
                <tbody>
                  {(entries.data?.items ?? []).map((r) => (
                    <tr key={r.id}><td className="nw num">{fmtDateTime(r.occurred_at)}</td><td>{r.entry_point ?? '—'}</td>
                      <td><div className="row" style={{ gap: 6 }}><ResultChip passed={r.passed} /><SourceChip source={r.source} /></div></td>
                      <td>{r.missing_labels.length ? <MissingChips labels={r.missing_labels} /> : <span className="mut">—</span>}</td></tr>
                  ))}
                  {entries.data && !entries.data.items.length && <tr><td colSpan={4} className="empty">No entries recorded.</td></tr>}
                </tbody>
              </table></div>
              {entries.data && <Pager page={page} pageSize={8} total={entries.data.total} onPage={setPage} />}
            </div>
          ) : (
            <div style={{ border: '1px solid var(--line)', borderRadius: 12 }} className="tw"><table className="tbl">
              <thead><tr><th>Time</th><th>Missing PPE</th><th>Severity</th><th>Status</th></tr></thead>
              <tbody>
                {(violations.data ?? []).map((v) => (
                  <tr key={v.id}><td className="nw num">{fmtDateTime(v.created_at)}</td><td><MissingChips labels={v.missing_labels} /></td>
                    <td><SeverityChip severity={v.severity} /></td><td><ViolationChip status={v.status} /></td></tr>
                ))}
                {violations.data && !violations.data.length && <tr><td colSpan={4} className="empty">No violations — fully compliant.</td></tr>}
              </tbody>
            </table></div>
          )}
        </>
      )}
    </Modal>
  );
}
