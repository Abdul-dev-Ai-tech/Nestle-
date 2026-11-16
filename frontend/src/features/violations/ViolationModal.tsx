import { ImageOff } from 'lucide-react';
import { useState } from 'react';
import { EmployeeCell, MissingChips, ModuleChip, SeverityChip, SimTag, Spinner, ViolationChip, VIOLATION_STATUS } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { apiUrl, patch, post } from '@/services/api';
import type { Violation } from '@/types';
import { fmtDateLong, fmtDateTime, fmtTime } from '@/utils/format';

export function ViolationModal({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const manage = can('violations.manage');
  const { data: v, reload } = useApi<Violation>(`/violations/${id}`);
  const [note, setNote] = useState('');

  async function setStatus(status: Violation['status']) {
    try { await patch(`/violations/${id}`, { status }); toast.ok(`Violation #${id} marked ${VIOLATION_STATUS[status][1].toLowerCase()}.`); reload(); onChanged(); } catch (e) { toast.error(e); }
  }
  async function addNote() {
    if (note.trim().length < 3) return toast.toast('Write a short note first.');
    try { await post(`/violations/${id}/notes`, { text: note.trim() }); setNote(''); reload(); } catch (e) { toast.error(e); }
  }

  return (
    <Modal title={`Violation #${id}`} wide onClose={onClose}
      footer={<>{manage && v && (['under_review', 'escalated', 'resolved'] as const).filter((s) => s !== v.status).map((s) => (
        <button key={s} className={`btn ${s === 'resolved' ? 'ok' : ''}`} onClick={() => setStatus(s)}>Mark {VIOLATION_STATUS[s][1].toLowerCase()}</button>))}
        <button className="btn pri" onClick={onClose}>Close</button></>}>
      {!v ? <Spinner /> : (
        <>
          <div className="g g2">
            <div>
              {v.has_evidence
                ? <img className="ev" src={apiUrl(`/entries/${v.entry_id}/evidence`)} alt="Evidence frame captured at the entry point" />
                : <div className="ev" style={{ aspectRatio: '16/9', display: 'grid', placeItems: 'center', color: '#cbbfae', textAlign: 'center', padding: 16 }}>
                  <div><ImageOff size={30} /><div className="sm" style={{ marginTop: 6 }}>No evidence image is stored for this record{v.source === 'sample' ? ' (seeded sample data)' : ''}.</div></div></div>}
              <p className="xs mut" style={{ marginTop: 6 }}>Evidence images are stored privately on the server; every view is written to the audit log.</p>
            </div>
            <div className="col" style={{ gap: 6 }}>
              <EmployeeCell employee={v.employee} />
              <div className="kv"><span>Status</span><ViolationChip status={v.status} /></div>
              <div className="kv"><span>Severity</span><span><SeverityChip severity={v.severity} />{v.is_repeat && <span className="chip bad" style={{ marginLeft: 6 }}>Repeat</span>}</span></div>
              <div className="kv"><span>Missing PPE</span><span><MissingChips labels={v.missing_labels} /></span></div>
              <div className="kv"><span>Date &amp; time</span><span>{fmtDateLong(v.created_at)}, {fmtTime(v.created_at)}</span></div>
              <div className="kv"><span>Camera / entry point</span><span>{v.camera ?? 'No camera recorded'} · {v.entry_point ?? '—'}</span></div>
              <div className="kv"><span>Factory module</span><ModuleChip module={v.module} /></div>
              <div className="kv"><span>Door action</span><span className="chip bad">Access denied</span></div>
              {v.employee_violation_count !== undefined && <div className="kv"><span>Employee violations (all time)</span><span className={v.employee_violation_count >= 3 ? 'dn' : ''}>{v.employee_violation_count}</span></div>}
              <div className="xs mut b" style={{ marginTop: 6 }}>DETECTION DETAIL {v.source !== 'live' && <SimTag label={v.source === 'sample' ? 'Sample data' : 'Simulated'} />}</div>
              {(v.item_results ?? []).filter((i) => i.required).map((i) => (
                <div className="kv" key={i.item}><span>{v.detections?.find((d) => d.item === i.item)?.label ?? i.item}</span>
                  <span className={i.status === 'pass' ? 'up' : 'dn'}>{i.status === 'pass' ? 'Detected' : 'Missing'} · {Math.round(i.confidence * 100)}%</span></div>
              ))}
              {!v.item_results?.length && <div className="sm mut">No per-item detection data for this record.</div>}
            </div>
          </div>
          <h3 style={{ margin: '14px 0 8px' }}>Review notes</h3>
          {(v.notes ?? []).map((n) => (
            <div key={n.id} className="sm" style={{ padding: '8px 10px', background: '#FBF8F2', borderRadius: 10, marginBottom: 6 }}><b>{n.author}</b> <span className="mut">· {fmtDateTime(n.created_at)}</span><br />{n.text}</div>
          ))}
          {!v.notes?.length && <div className="sm mut">No notes yet.</div>}
          {manage ? (
            <div className="row" style={{ marginTop: 8 }}><input className="in" maxLength={500} placeholder="Add a review note" value={note} onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && addNote()} /><button className="btn" onClick={addNote}>Add</button></div>
          ) : <p className="sm mut" style={{ marginTop: 8 }}>Your role can view violations but not change their status.</p>}
        </>
      )}
    </Modal>
  );
}
