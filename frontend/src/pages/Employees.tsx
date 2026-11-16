import { ArrowDown, ArrowUp, Eye, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { EmployeeCell, ErrorBanner, ModuleChip, Pager, Seg, Spinner } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { EmployeeForm } from '@/features/employees/EmployeeForm';
import { EmployeeProfile } from '@/features/employees/EmployeeProfile';
import { useApi } from '@/hooks/useApi';
import { del } from '@/services/api';
import type { Employee, Page } from '@/types';
import { fmtNum, fmtPct } from '@/utils/format';

type List = Page<Employee> & { summary: { total: number; active: number; inactive: number } };
const PAGE_SIZE = 10;

export default function Employees() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const manage = can('employees.manage');
  const [q, setQ] = useState('');
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<'all' | 'active' | 'inactive'>('all');
  const [dept, setDept] = useState('all');
  const [sort, setSort] = useState<{ key: string; order: 'asc' | 'desc' }>({ key: 'name', order: 'asc' });
  const [page, setPage] = useState(1);
  const [form, setForm] = useState<Employee | 'new' | null>(null);
  const [profile, setProfile] = useState<number | null>(null);
  const [remove, setRemove] = useState<Employee | null>(null);

  useEffect(() => { const t = setTimeout(() => { setSearch(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);
  useEffect(() => setPage(1), [status, dept, scope.moduleId, scope.factoryId]);

  const departments = useApi<{ id: number; name: string }[]>(scope.factoryId ? '/departments' : null, { factory_id: scope.factoryId ?? undefined });
  const list = useApi<List>(scope.factoryId ? '/employees' : null, {
    ...scope.params, q: search, status, department_id: dept, sort: sort.key, order: sort.order, page, page_size: PAGE_SIZE,
  });

  const th = (key: string, label: string, right?: boolean) => (
    <th className={`th-sort ${right ? 'r' : ''}`} onClick={() => setSort((s) => ({ key, order: s.key === key && s.order === 'asc' ? 'desc' : 'asc' }))}
      aria-sort={sort.key === key ? (sort.order === 'asc' ? 'ascending' : 'descending') : 'none'}>
      {label} {sort.key === key && (sort.order === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
    </th>
  );

  async function confirmRemove() {
    if (!remove) return;
    try {
      const r = await del<{ result: string }>(`/employees/${remove.id}`);
      toast.ok(r.result === 'deleted' ? 'Employee deleted.' : 'Employee has entry history, so the record was deactivated instead of deleted.');
      setRemove(null);
      list.reload();
    } catch (e) {
      toast.error(e);
    }
  }

  const s = list.data?.summary;
  return (
    <>
      <PageHeader title="Employee management" description={s ? `${fmtNum(s.total)} employees · ${fmtNum(s.active)} active` : 'People allowed to request entry.'}
        actions={<button className="btn pri" disabled={!manage} title={manage ? '' : 'Your role cannot add employees'} onClick={() => setForm('new')}><Plus size={16} /> Add employee</button>} />
      {list.error && <ErrorBanner message={list.error} onRetry={list.reload} />}
      <div className="card">
        <div className="fbar" style={{ padding: '14px 16px 0' }}>
          <div className="inw"><Search size={16} className="ic" /><input className="in" placeholder="Search name, ID, designation" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search employees" /></div>
          <select className="in" value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department">
            <option value="all">All departments</option>{(departments.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <Seg value={status} onChange={setStatus} options={[['all', 'All'], ['active', 'Active'], ['inactive', 'Inactive']]} />
        </div>
        {list.loading && !list.data ? <Spinner /> : (
          <>
            <div className="tw">
              <table className="tbl">
                <thead><tr>{th('name', 'Employee')}<th>Department</th><th>Assigned module</th>{th('shift', 'Shift')}<th className="r">Entries (30d)</th><th className="r">Compliance</th>{th('status', 'Status')}<th /></tr></thead>
                <tbody>
                  {(list.data?.items ?? []).map((e) => (
                    <tr key={e.id} className="clk" onClick={() => setProfile(e.id)}>
                      <td><EmployeeCell employee={{ ...e, department: e.department }} /></td>
                      <td>{e.department ?? '—'}</td><td><ModuleChip module={e.module} /></td><td>{e.shift}</td>
                      <td className="r num">{e.stats_30d?.entries ?? 0}</td>
                      <td className={`r num b ${(e.stats_30d?.compliance ?? 100) < 92 ? 'dn' : ''}`}>{fmtPct(e.stats_30d?.compliance)}</td>
                      <td>{e.status === 'active' ? <span className="chip ok">Active</span> : <span className="chip">Inactive</span>}</td>
                      <td className="r nw" onClick={(ev) => ev.stopPropagation()}>
                        <button className="btn s gh icn" aria-label={`View ${e.full_name}`} onClick={() => setProfile(e.id)}><Eye size={15} /></button>
                        <button className="btn s gh icn" aria-label={`Edit ${e.full_name}`} disabled={!manage} onClick={() => setForm(e)}><Pencil size={15} /></button>
                        <button className="btn s gh icn" aria-label={`Delete ${e.full_name}`} disabled={!manage} onClick={() => setRemove(e)}><Trash2 size={15} /></button>
                      </td>
                    </tr>
                  ))}
                  {list.data && !list.data.items.length && <tr><td colSpan={8} className="empty">No employees match these filters.</td></tr>}
                </tbody>
              </table>
            </div>
            {list.data && <Pager page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={setPage} />}
          </>
        )}
      </div>
      {form && <EmployeeForm employee={form === 'new' ? null : form} departments={departments.data ?? []} onClose={() => setForm(null)} onSaved={() => { setForm(null); list.reload(); }} />}
      {profile && <EmployeeProfile id={profile} onClose={() => setProfile(null)} onChanged={list.reload} onEdit={(e) => { setProfile(null); setForm(e); }} />}
      {remove && (
        <Modal title="Delete employee?" onClose={() => setRemove(null)}
          footer={<><button className="btn" onClick={() => setRemove(null)}>Cancel</button><button className="btn dan" onClick={confirmRemove}>Delete or deactivate</button></>}>
          <p><b>{remove.full_name}</b> ({remove.employee_code}) will be removed.</p>
          <p className="sm mut" style={{ marginTop: 8 }}>If this person has entry history, the record is kept for the audit trail and switched to inactive instead of being deleted.</p>
        </Modal>
      )}
    </>
  );
}
