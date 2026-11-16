import { useState } from 'react';
import { Field, Switch } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { patch, post } from '@/services/api';
import type { Employee } from '@/types';

export function EmployeeForm({ employee, departments, onClose, onSaved }: {
  employee: Employee | null; departments: { id: number; name: string }[]; onClose: () => void; onSaved: () => void;
}) {
  const scope = useScope();
  const toast = useToast();
  interface FormState { employee_code: string; full_name: string; designation: string; department_id: number | null; module_id: number | null; shift: string; beard_net_applicable: boolean; status: 'active' | 'inactive' }
  const [f, setF] = useState<FormState>({
    employee_code: employee?.employee_code ?? '', full_name: employee?.full_name ?? '', designation: employee?.designation ?? '',
    department_id: employee?.department_id ?? departments[0]?.id ?? null, module_id: employee?.module_id ?? scope.moduleId ?? scope.modules[0]?.id ?? null,
    shift: employee?.shift ?? scope.factory?.shifts[0]?.code ?? 'A', beard_net_applicable: employee?.beard_net_applicable ?? false,
    status: employee?.status ?? 'active',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF((s) => ({ ...s, [k]: v }));

  async function save() {
    if (!/^[A-Za-z0-9-]{3,20}$/.test(f.employee_code.trim())) return setError('Employee ID must be 3–20 letters, numbers or dashes (e.g. NPK-10432).');
    if (f.full_name.trim().length < 3) return setError('Enter the full name.');
    setError('');
    setBusy(true);
    try {
      if (employee) {
        const { employee_code: _code, ...rest } = f;
        void _code;
        await patch(`/employees/${employee.id}`, rest);
      } else {
        await post('/employees', f, { factory_id: scope.factoryId ?? undefined });
      }
      toast.ok(employee ? 'Employee updated.' : 'Employee added.');
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={employee ? 'Edit employee' : 'Add employee'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn pri" onClick={save} disabled={busy}>{employee ? 'Save changes' : 'Add employee'}</button></>}>
      <div className="g g2">
        <Field label="Employee ID"><input className="in" value={f.employee_code} disabled={!!employee} maxLength={20} onChange={(e) => set('employee_code', e.target.value)} /></Field>
        <Field label="Full name"><input className="in" value={f.full_name} maxLength={120} placeholder="e.g. Ahmed Khan" onChange={(e) => set('full_name', e.target.value)} /></Field>
        <Field label="Department">
          <select className="in" value={f.department_id ?? ''} onChange={(e) => set('department_id', e.target.value ? Number(e.target.value) : null)}>
            <option value="">— None —</option>{departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        </Field>
        <Field label="Designation"><input className="in" value={f.designation} maxLength={80} placeholder="e.g. Line Operator" onChange={(e) => set('designation', e.target.value)} /></Field>
        <Field label="Assigned factory"><input className="in" value={scope.factory?.name ?? ''} disabled /></Field>
        <Field label="Assigned module">
          <select className="in" value={f.module_id ?? ''} onChange={(e) => set('module_id', e.target.value ? Number(e.target.value) : null)}>
            <option value="">— None —</option>{scope.modules.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </Field>
        <Field label="Shift">
          <select className="in" value={f.shift} onChange={(e) => set('shift', e.target.value)}>
            {(scope.factory?.shifts ?? []).map((s) => <option key={s.code} value={s.code}>Shift {s.code} ({s.start}–{s.end})</option>)}
          </select>
        </Field>
      </div>
      <div className="row wrap" style={{ marginTop: 14, gap: 18 }}>
        <label className="row sm" style={{ gap: 8 }}><Switch checked={f.status === 'active'} onChange={(v) => set('status', v ? 'active' : 'inactive')} label="Active" /> Active — allowed to request entry</label>
        <label className="row sm" style={{ gap: 8 }}><Switch checked={f.beard_net_applicable} onChange={(v) => set('beard_net_applicable', v)} label="Beard net applies" /> Beard net applies</label>
      </div>
      {error && <div className="errt" style={{ marginTop: 10 }} role="alert">{error}</div>}
    </Modal>
  );
}
