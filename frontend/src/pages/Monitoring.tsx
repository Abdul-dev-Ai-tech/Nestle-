import { AlertTriangle, Camera as CameraIcon, Download, Play, ScanLine, Search, Square, Video, X as XIcon } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ErrorBanner, Field, Switch } from '@/components/ui/basic';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { ResultPanel } from '@/features/monitoring/ResultPanel';
import { useApi } from '@/hooks/useApi';
import { useCamera } from '@/hooks/useCamera';
import { apiUrl, get, getBlob, postForm } from '@/services/api';
import type { AiStatus, Camera, CheckResult, Door, Employee, FactorySettings } from '@/types';
import { fmtTime } from '@/utils/format';

interface Capture { url: string; at: string; source: string }
const AUTO_SECONDS = 7;

export default function Monitoring() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const operate = can('monitoring.operate');
  const status = useApi<AiStatus>('/monitoring/status');
  const cameras = useApi<Camera[]>(scope.factoryId ? '/cameras' : null, { factory_id: scope.factoryId ?? undefined });
  const doors = useApi<Door[]>(scope.factoryId ? '/access/doors' : null, { factory_id: scope.factoryId ?? undefined }, 4000);
  const settings = useApi<FactorySettings>(can('settings.view') && scope.factoryId ? '/settings' : null, { factory_id: scope.factoryId ?? undefined });
  const cam = useCamera();

  const entryPoints = useMemo(() => scope.modules.filter((m) => m.is_active && (!scope.moduleId || m.id === scope.moduleId))
    .flatMap((m) => m.entry_points.filter((e) => e.is_active).map((e) => ({ ...e, module: m }))), [scope.modules, scope.moduleId]);
  const backendCams = useMemo(() => (cameras.data ?? []).filter((c) => c.type !== 'browser' && c.is_active), [cameras.data]);

  const [source, setSource] = useState('b:user');
  const [entryPointId, setEntryPointId] = useState<number | null>(null);
  const [streamOn, setStreamOn] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [employeeCode, setEmployeeCode] = useState('');
  const [employee, setEmployee] = useState<Employee | null>(null);
  const [scenario, setScenario] = useState('random');
  const [result, setResult] = useState<CheckResult | null>(null);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [auto, setAuto] = useState(false);
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [streamNonce, setStreamNonce] = useState(0);

  const isBrowser = source.startsWith('b:');
  const backendCam = isBrowser ? null : backendCams.find((c) => c.id === Number(source.slice(2))) ?? null;
  const running = isBrowser ? cam.running : streamOn && !streamError;
  const entryPoint = entryPoints.find((e) => e.id === entryPointId) ?? null;
  const door = (doors.data ?? []).find((d) => d.entry_point_id === entryPointId) ?? null;
  const simulated = status.data?.simulated ?? false;

  useEffect(() => {
    if (!entryPoints.length) return setEntryPointId(null);
    if (!entryPoints.some((e) => e.id === entryPointId)) setEntryPointId(entryPoints[0].id);
  }, [entryPoints, entryPointId]);

  useEffect(() => {
    if (backendCam?.entry_point_id && entryPoints.some((e) => e.id === backendCam.entry_point_id)) setEntryPointId(backendCam.entry_point_id);
  }, [backendCam, entryPoints]);

  function stopAll() {
    cam.stop();
    setStreamOn(false);
    setStreamError(null);
  }

  function changeSource(value: string) {
    stopAll();
    setResult(null);
    setFrameUrl(null);
    setSource(value);
  }

  async function start() {
    setResult(null);
    setFrameUrl(null);
    if (isBrowser) await cam.start(source.slice(2));
    else {
      setStreamError(null);
      setStreamNonce((n) => n + 1);
      setStreamOn(true);
    }
  }

  const grabFrame = useCallback(async (): Promise<Blob | null> => {
    if (isBrowser) return cam.capture();
    if (!backendCam) return null;
    return getBlob(`/cameras/${backendCam.id}/snapshot`);
  }, [isBrowser, backendCam, cam]);

  async function capture() {
    try {
      const blob = await grabFrame();
      if (!blob) return toast.toast('The camera is still starting — try again in a moment.');
      setCaptures((c) => [{ url: URL.createObjectURL(blob), at: new Date().toISOString(), source: isBrowser ? 'Browser camera' : backendCam?.name ?? 'Camera' }, ...c].slice(0, 12));
      toast.ok('Image captured.');
    } catch (e) {
      toast.error(e);
    }
  }

  async function lookup() {
    setEmployee(null);
    if (!employeeCode.trim()) return;
    try {
      setEmployee(await get<Employee>('/employees/lookup', { code: employeeCode.trim(), factory_id: scope.factoryId ?? undefined }));
    } catch (e) {
      toast.error(e);
    }
  }

  const runCheck = useCallback(async () => {
    if (!entryPointId || busy) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.set('entry_point_id', String(entryPointId));
      form.set('scenario', status.data?.can_force_scenario ? scenario : 'random');
      if (employeeCode.trim()) form.set('employee_code', employeeCode.trim());
      let blob: Blob | null = null;
      if (isBrowser) {
        blob = await cam.capture();
        if (!blob) throw new Error('The camera is not delivering video yet.');
        form.set('frame', blob, 'frame.jpg');
        const linked = (cameras.data ?? []).find((c) => c.type === 'browser' && c.entry_point_id === entryPointId);
        if (linked) form.set('camera_id', String(linked.id));
      } else if (backendCam) {
        form.set('camera_id', String(backendCam.id));
      }
      const res = await postForm<CheckResult>('/monitoring/check', form);
      setResult(res);
      setFrameUrl(blob ? URL.createObjectURL(blob) : res.entry.has_evidence && can('violations.view') ? apiUrl(`/entries/${res.entry.id}/evidence`) : null);
      doors.reload();
      if (!res.passed) toast.toast(`Violation: ${res.employee?.full_name ?? 'Unidentified person'} — missing ${res.missing_labels.join(', ')}`, 'bad');
    } catch (e) {
      toast.error(e);
      setAuto(false);
    } finally {
      setBusy(false);
    }
  }, [entryPointId, busy, status.data, scenario, employeeCode, isBrowser, cam, cameras.data, backendCam, can, doors, toast]);

  const runRef = useRef(runCheck);
  runRef.current = runCheck;
  useEffect(() => {
    if (!auto || !running) return;
    const t = window.setInterval(() => runRef.current(), AUTO_SECONDS * 1000);
    return () => window.clearInterval(t);
  }, [auto, running]);

  const stageClass = result && running ? (result.passed ? 'p' : 'f') : '';
  const boxes = result?.items.filter((i) => i.required && i.bbox) ?? [];

  return (
    <>
      <PageHeader title="Live AI monitoring" description="Check PPE at the entry point. The door opens only when the result is PASS." />
      {status.error && <ErrorBanner message={status.error} onRetry={status.reload} />}
      {status.data && simulated && (
        <div className="banner sim"><AlertTriangle size={16} /><div><b>AI simulation mode.</b> The camera preview is real, but PPE results and confidence values are produced by a simulated detector — the image is not analysed. Results are stored as “simulated” and can never operate real door hardware. See docs/AI_MODEL.md to train and load a real model.</div></div>
      )}
      {status.data && !status.data.available && (
        <div className="banner err"><AlertTriangle size={16} /><div><b>AI detection is not available.</b> {status.data.error} PPE checks are disabled until a trained model is configured.</div></div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="cb row wrap" style={{ alignItems: 'flex-end', gap: 14 }}>
          <div className="grow" style={{ minWidth: 230 }}>
            <Field label="1 · Camera source">
              <select className="in" value={source} onChange={(e) => changeSource(e.target.value)}>
                <optgroup label="This device (browser)">
                  <option value="b:user">Laptop webcam / front camera</option>
                  <option value="b:environment">Mobile rear camera</option>
                  {cam.devices.map((d, i) => <option key={d.deviceId} value={`b:${d.deviceId}`}>{d.label || `Camera ${i + 1}`}</option>)}
                </optgroup>
                {backendCams.length > 0 && (
                  <optgroup label="Server cameras (USB / IP / RTSP)">
                    {backendCams.map((c) => <option key={c.id} value={`c:${c.id}`}>{c.name} — {c.type.toUpperCase()}</option>)}
                  </optgroup>
                )}
              </select>
            </Field>
          </div>
          <div className="grow" style={{ minWidth: 230 }}>
            <Field label="2 · Entry point being monitored">
              <select className="in" value={entryPointId ?? ''} disabled={!!backendCam?.entry_point_id} onChange={(e) => { setEntryPointId(Number(e.target.value)); setResult(null); }}>
                {entryPoints.map((e) => <option key={e.id} value={e.id}>{e.module.name} — {e.name}</option>)}
                {!entryPoints.length && <option value="">No entry points configured</option>}
              </select>
            </Field>
          </div>
          <div className="pills">
            <span className="pill">Camera {running
              ? <span className="chip ok"><span className="dot pulse" />Connected</span>
              : cam.error || streamError ? <span className="chip bad"><span className="dot" />Connection failed</span> : <span className="chip"><span className="dot" />Disconnected</span>}</span>
            <span className="pill">AI detection {!status.data?.available
              ? <span className="chip bad">Unavailable</span>
              : busy ? <span className="chip info"><span className="dot" />Analyzing frame…</span>
                : simulated ? <span className="chip warn">Ready · simulated</span> : <span className="chip ok">Ready · {status.data.model_version}</span>}</span>
          </div>
        </div>
      </div>

      <div className="g gmon">
        <div className="col" style={{ gap: 16 }}>
          <div className="card">
            <div className="cb">
              <div className={`stage ${stageClass}`}>
                {isBrowser && <video ref={cam.videoRef} autoPlay playsInline muted style={{ display: cam.running ? 'block' : 'none' }} />}
                {!isBrowser && streamOn && backendCam && !streamError && (
                  <img key={streamNonce} src={apiUrl(`/cameras/${backendCam.id}/stream`, { n: streamNonce })} alt="Live camera stream"
                    style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={() => setStreamError('The server could not read this camera. Check its address, credentials and network, then try again.')} />
                )}
                {running ? (
                  <>
                    <span className="ovl tl tag rec"><span className="dot" />LIVE · {isBrowser ? 'This device camera' : backendCam?.name}</span>
                    <span className="ovl tr2 tag"><ScanLine size={13} /> AI: {simulated ? 'simulated' : 'model'}</span>
                    <i className="cnr c1" /><i className="cnr c2" /><i className="cnr c3" /><i className="cnr c4" />
                    {busy && <div className="scan" />}
                    {result && !busy && (
                      <div className="ovl bl">
                        <span className="tag" style={{ background: result.passed ? 'rgba(23,128,79,.94)' : 'rgba(192,52,42,.94)', fontSize: 13, padding: '8px 13px' }}>
                          {result.passed ? 'PASS — access granted' : 'FAIL — access denied'}{result.detector.simulated ? ' · simulated result' : ''}
                        </span>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <span className="radar" /><span className="radar r2" />
                    <div className="idl" style={{ textAlign: 'center', padding: 20, maxWidth: 440 }}>
                      {cam.error || streamError ? (
                        <><div style={{ color: '#ff8a80' }}><AlertTriangle size={34} /></div>
                          <b style={{ display: 'block', color: '#fff', margin: '8px 0 4px' }}>{cam.error?.title ?? 'Camera stream failed'}</b>
                          <span className="sm">{cam.error?.detail ?? streamError}</span></>
                      ) : (
                        <><Video size={38} /><b style={{ display: 'block', color: '#fff', margin: '8px 0 4px' }}>Camera is stopped</b>
                          <span className="sm">{isBrowser ? 'Press Start camera. Your browser will ask for permission.' : 'Press Start camera to relay this camera through the server.'}</span></>
                      )}
                    </div>
                  </>
                )}
              </div>
              <div className="ctrl">
                <button className="btn ok lg" onClick={start} disabled={!operate || running}><Play size={16} /> Start camera</button>
                <button className="btn lg" onClick={stopAll} disabled={!operate || (!running && !streamOn)}><Square size={15} /> Stop camera</button>
                <button className="btn lg" id="bCap" onClick={capture} disabled={!operate || !running}><CameraIcon size={16} /> Capture image</button>
                <button className="btn pri lg wide" onClick={runCheck} disabled={!operate || !running || busy || !entryPointId || !status.data?.available}>
                  <ScanLine size={16} /> {busy ? 'Checking…' : simulated ? 'Run PPE check (simulated)' : 'Run PPE check'}
                </button>
              </div>
              <div className="row wrap sm" style={{ marginTop: 14, gap: 16, paddingTop: 14, borderTop: '1px solid var(--line2)', alignItems: 'flex-end' }}>
                <div style={{ minWidth: 220 }} className="grow">
                  <Field label="3 · Employee ID (badge or typed) — optional">
                    <div className="row">
                      <input className="in" placeholder="e.g. NPK-10231" maxLength={20} value={employeeCode}
                        onChange={(e) => { setEmployeeCode(e.target.value); setEmployee(null); }} onKeyDown={(e) => e.key === 'Enter' && lookup()} />
                      <button className="btn" onClick={lookup} disabled={!employeeCode.trim()}><Search size={15} /> Find</button>
                      {employeeCode && <button className="btn gh icn" aria-label="Clear" onClick={() => { setEmployeeCode(''); setEmployee(null); }}><XIcon size={16} /></button>}
                    </div>
                  </Field>
                  {employee && <div className="xs" style={{ marginTop: 5 }}><b>{employee.full_name}</b> · {employee.designation} · {employee.status === 'active' ? 'Active' : <span className="dn">Inactive</span>}</div>}
                </div>
                <label className="row" style={{ gap: 8 }}><Switch checked={auto} onChange={setAuto} disabled={!operate} label="Auto-check" /> Auto-check every {AUTO_SECONDS} s</label>
                {status.data?.can_force_scenario && (
                  <label className="row" style={{ gap: 8 }}>Test scenario
                    <select className="in" style={{ width: 'auto', height: 34 }} value={scenario} onChange={(e) => setScenario(e.target.value)}>
                      <option value="random">Random</option><option value="pass">Force PASS</option><option value="fail">Force FAIL</option>
                    </select>
                  </label>
                )}
                {!operate && <span className="chip warn">Your role is view-only here</span>}
              </div>
            </div>
          </div>

          {frameUrl && result && (
            <div className="card">
              <div className="ch"><div><h3>Analysed frame</h3><p>{boxes.length ? 'Boxes show where each item was detected' : result.detector.simulated ? 'Simulated result — no detection boxes are drawn' : 'No bounding boxes were returned for this frame'}</p></div></div>
              <div className="cb"><div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', background: '#14100D' }}>
                <img src={frameUrl} alt="Analysed frame" style={{ display: 'block', width: '100%' }} />
                {boxes.map((b) => (
                  <div key={b.item} className={`bbox ${b.status === 'fail' ? 'bad' : ''}`}
                    style={{ left: `${b.bbox![0] * 100}%`, top: `${b.bbox![1] * 100}%`, width: `${b.bbox![2] * 100}%`, height: `${b.bbox![3] * 100}%` }}>
                    <span>{b.label} {Math.round(b.confidence * 100)}%</span>
                  </div>
                ))}
              </div></div>
            </div>
          )}

          <div className="card">
            <div className="ch"><div><h3>Captured images</h3><p>Kept in this browser tab only — not uploaded</p></div></div>
            <div className="cb">
              {captures.length ? (
                <div className="caps">
                  {captures.map((c) => (
                    <figure key={c.url}>
                      <a href={c.url} download={`capture_${c.at.replace(/[:.]/g, '-')}.jpg`} title="Download"><img src={c.url} alt="Capture" /></a>
                      <figcaption><Download size={11} /> {fmtTime(c.at)} · {c.source}</figcaption>
                    </figure>
                  ))}
                </div>
              ) : <div className="sm mut">No captures yet. Start a camera and press Capture image.</div>}
            </div>
          </div>
        </div>
        <div className="col" style={{ gap: 16 }}>
          <ResultPanel result={result} module={entryPoint?.module ?? null} door={door} threshold={settings.data?.confidence_threshold} />
        </div>
      </div>
    </>
  );
}
