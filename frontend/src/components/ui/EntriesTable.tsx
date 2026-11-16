import type { Entry } from '@/types';
import { fmtDateTime, fmtTime } from '@/utils/format';
import { DecisionChip, EmployeeCell, MissingChips, ModuleChip, ResultChip, SourceChip } from './basic';

export function EntriesTable({ rows, full, empty = 'No entries.' }: { rows: Entry[]; full?: boolean; empty?: string }) {
  return (
    <div className="tw">
      <table className="tbl">
        <thead><tr><th>Time</th><th>Employee</th><th>Module / entry point</th><th>Result</th><th>Door</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="nw num">{full ? fmtDateTime(r.occurred_at) : fmtTime(r.occurred_at)}</td>
              <td><EmployeeCell employee={r.employee} /></td>
              <td><ModuleChip module={r.module} /><div className="xs mut" style={{ marginTop: 3 }}>{r.entry_point ?? '—'}</div></td>
              <td>
                <div className="row" style={{ gap: 6 }}><ResultChip passed={r.passed} /><SourceChip source={r.source} /></div>
                {!r.passed && <div style={{ marginTop: 4 }}><MissingChips labels={r.missing_labels} /></div>}
              </td>
              <td><DecisionChip decision={r.decision} /></td>
            </tr>
          ))}
          {!rows.length && <tr><td colSpan={5} className="empty">{empty}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
