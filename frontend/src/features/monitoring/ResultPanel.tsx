import { Check, ScanLine, X } from 'lucide-react';
import { Avatar, DoorVisual, PpeStateIcon, SimTag, doorLabel } from '@/components/ui/basic';
import type { CheckResult, Door, ItemResult, Module } from '@/types';
import { PPE_ITEMS, PPE_LABELS } from '@/types';
import { fmtTime } from '@/utils/format';

function Row({ item, state }: { item: ItemResult | { label: string }; state: 'ok' | 'bad' | 'na' }) {
  const r = 'confidence' in item ? item : null;
  return (
    <div className="ppe">
      <PpeStateIcon state={state} />
      <div>
        <div className="b sm">{item.label}</div>
        {r ? (
          <>
            <div className="cf"><i style={{ width: `${Math.round(r.confidence * 100)}%`, background: `var(--${state === 'ok' ? 'pass' : 'fail'})` }} /></div>
            {r.reason && <div className="xs mut" style={{ marginTop: 3 }}>{r.reason}</div>}
          </>
        ) : <div className="xs mut">Will be checked</div>}
      </div>
      <span className={`sm b num ${state === 'ok' ? 'up' : state === 'bad' ? 'dn' : 'mut'}`}>{r ? `${Math.round(r.confidence * 100)}%` : '—'}</span>
    </div>
  );
}

/** Large PASS/FAIL result, entry authorization, detected and missing PPE, employee. */
export function ResultPanel({ result, module, door, threshold }: { result: CheckResult | null; module: Module | null; door: Door | null; threshold?: number }) {
  const required = result ? result.items.filter((i) => i.required) : [];
  const detected = required.filter((i) => i.status === 'pass');
  const missing = required.filter((i) => i.status === 'fail');
  const notRequired = result
    ? result.items.filter((i) => !i.required).map((i) => i.label)
    : PPE_ITEMS.filter((i) => !module?.ppe[i]?.required).map((i) => PPE_LABELS[i]);
  const shownDoor = result?.door ?? door;
  const sim = result?.detector.simulated;
  return (
    <>
      <div className="card">
        <div className="ch"><h3>Compliance result</h3>{sim && <SimTag />}</div>
        <div className="cb">
          <div className={`res ${result ? (result.passed ? 'p' : 'f') : 'n'}`} data-testid="result">
            {result ? (result.passed
              ? <><Check size={38} />PASS<small>All required PPE detected</small></>
              : <><X size={38} />FAIL<small>{missing.length} required item{missing.length === 1 ? '' : 's'} missing</small></>)
              : <>Waiting for a check<small style={{ fontWeight: 500 }}>Start the camera, then run a PPE check</small></>}
          </div>
          <div className="authz" style={{ background: result ? (result.passed ? 'var(--passbg)' : 'var(--failbg)') : '#F3ECE0' }}>
            <DoorVisual door={shownDoor} />
            <div>
              <div className="xs b mut" style={{ letterSpacing: '.09em' }}>ENTRY AUTHORIZATION</div>
              <div className="b" style={{ fontFamily: 'var(--fh)', fontSize: 17, color: result ? (result.passed ? 'var(--pass)' : 'var(--fail)') : 'var(--ink)' }}>
                {result ? (result.passed ? 'Access granted' : 'Access denied') : 'Awaiting check'}
              </div>
              <div className="sm mut">
                {result ? result.door_result.message : shownDoor ? `${shownDoor.name} — ${doorLabel(shownDoor).toLowerCase()} until a PASS result` : 'No door linked to this entry point'}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="cb">
          {result ? (
            <>
              <div className="sect" style={{ color: 'var(--pass)' }}><Check size={13} /> Detected PPE ({detected.length})</div>
              {detected.map((i) => <Row key={i.item} item={i} state="ok" />)}
              {!detected.length && <div className="sm mut" style={{ padding: '4px 0 8px' }}>No required item was detected.</div>}
              <div className="sect" style={{ color: 'var(--fail)', marginTop: 16 }}><X size={13} /> Missing PPE ({missing.length})</div>
              {missing.map((i) => <Row key={i.item} item={i} state="bad" />)}
              {!missing.length && <span className="chip ok">None — fully compliant</span>}
            </>
          ) : (
            <>
              <div className="sect"><ScanLine size={13} /> Required PPE at this entry point</div>
              {PPE_ITEMS.filter((i) => module?.ppe[i]?.required).map((i) => <Row key={i} item={{ label: PPE_LABELS[i] }} state="na" />)}
              {!PPE_ITEMS.some((i) => module?.ppe[i]?.required) && <div className="sm mut">No PPE rules set for this module.</div>}
            </>
          )}
          {notRequired.length > 0 && <div className="xs mut" style={{ marginTop: 12 }}>Not required here: {notRequired.join(', ')}</div>}
        </div>
      </div>

      <div className="card">
        <div className="ch"><h3>Employee &amp; entry</h3></div>
        <div className="cb">
          {result?.employee ? (
            <div className="row" style={{ marginBottom: 14 }}>
              <Avatar name={result.employee.full_name} large photoEmployeeId={result.employee.has_photo ? result.employee.id : undefined} />
              <div>
                <div className="b" style={{ fontSize: 15.5 }}>{result.employee.full_name}</div>
                <div className="sm mut">{result.employee.employee_code} · {result.employee.designation}</div>
                <div className="sm mut">{result.employee.department ?? '—'} · Shift {result.employee.shift}</div>
              </div>
            </div>
          ) : <div className="sm mut" style={{ marginBottom: 12 }}>{result ? 'Unidentified person — no employee ID was entered.' : 'No check has been run yet.'}</div>}
          <div className="kv"><span>Confidence threshold</span><span>{Math.round((result?.threshold ?? threshold ?? 0.6) * 100)}%</span></div>
          {result && (
            <>
              <div className="kv"><span>Entry record</span><span>#{result.entry.id} · {fmtTime(result.entry.occurred_at)}</span></div>
              <div className="kv"><span>Detector</span><span>{result.detector.model_name} {result.detector.model_version}</span></div>
              <div className="kv"><span>Door action</span><span>{result.door_result.action.replace('_', ' ')}{result.door_result.simulated ? ' (simulated)' : ''}</span></div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
