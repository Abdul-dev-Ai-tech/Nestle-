import { Camera as CameraIcon, Eye, Info, Pencil, Plus, Radar, RefreshCw, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { CameraStatusChip, ErrorBanner, Field, Kpi, Spinner, Switch } from '@/components/ui/basic';
import { Modal } from '@/components/ui/Modal';
import { PageHeader } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { useCamera } from '@/hooks/useCamera';
import { apiUrl, del, post, put } from '@/services/api';
import type { Camera } from '@/types';
import { ago } from '@/utils/format';

const TYPE_LABEL: Record<Camera['type'], string> = { browser: 'Browser (laptop / mobile)', usb: 'USB webcam (on server)', rtsp: 'IP camera (RTSP)', onvif: 'ONVIF IP camera' };
interface Device { ip: string; name: string; service_urls: string[] }

function CameraForm({ camera, preset, onClose, onSaved }: { camera: Camera | null; preset?: Partial<Camera>; onClose: () => void; onSaved: () => void }) {
  const scope = useScope();
  const toast = useToast();
  const [f, setF] = useState({
    name: camera?.name ?? preset?.name ?? '', type: camera?.type ?? preset?.type ?? 'rtsp', source: camera?.source ?? preset?.source ?? '',
    entry_point_id: camera?.entry_point_id ?? null as number | null, is_active: camera?.is_active ?? true, username: '', password: '', clear_credentials: false,
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const network = f.type === 'rtsp' || f.type === 'onvif';

  async function save() {
    if (f.name.trim().length < 3) return setError('Camera name is required.');
    if (network && !/^(rtsps?|https?):\/\/[^\s@]+$/i.test(f.source.trim())) return setError('Enter the stream address without a username or password, e.g. rtsp://10.20.30.40:554/stream1');
    if (f.type === 'usb' && !/^\d{1,2}$/.test(f.source.trim())) return setError('USB cameras use a device number such as 0 or 1.');
    setBusy(true);
    const body = { ...f, name: f.name.trim(), source: f.type === 'browser' ? '' : f.source.trim(), username: f.username || null, password: f.username ? f.password : null };
    try {
      if (camera) await put(`/cameras/${camera.id}`, body);
      else await post('/cameras', body, { factory_id: scope.factoryId ?? undefined });
      toast.ok(camera ? 'Camera updated.' : 'Camera added.');
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={camera ? 'Edit camera' : 'Add camera'} onClose={onClose}
      footer={<><button className="btn" onClick={onClose}>Cancel</button><button className="btn pri" disabled={busy} onClick={save}>{camera ? 'Save changes' : 'Add camera'}</button></>}>
      <div className="col" style={{ gap: 12 }}>
        <Field label="Camera name"><input className="in" maxLength={80} placeholder="e.g. Gate A overview" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Camera type">
          <select className="in" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value as Camera['type'], source: '' })}>
            {(Object.keys(TYPE_LABEL) as Camera['type'][]).map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
          </select>
        </Field>
        {f.type === 'browser' && <div className="note i"><Info size={16} /><div>Browser cameras are opened on the operator’s own laptop or phone from the Live AI Monitoring page. Nothing is configured on the server.</div></div>}
        {f.type === 'usb' && <Field label="USB device number" hint="0 is the first camera plugged into the machine running the backend."><input className="in" maxLength={2} placeholder="0" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} /></Field>}
        {network && (
          <>
            <Field label="Stream address" hint="Without credentials. They are entered below and stored encrypted."><input className="in" maxLength={300} placeholder="rtsp://10.20.30.40:554/stream1" value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} /></Field>
            <div className="g g2">
              <Field label="Camera username"><input className="in" autoComplete="off" maxLength={80} placeholder={camera?.has_credentials ? '(unchanged)' : ''} value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} /></Field>
              <Field label="Camera password"><input className="in" type="password" autoComplete="new-password" maxLength={120} placeholder={camera?.has_credentials ? '(unchanged)' : ''} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
            </div>
            {camera?.has_credentials && <label className="row sm" style={{ gap: 8 }}><input type="checkbox" checked={f.clear_credentials} onChange={(e) => setF({ ...f, clear_credentials: e.target.checked })} /> Remove the stored credentials</label>}
          </>
        )}
        <Field label="Entry point">
          <select className="in" value={f.entry_point_id ?? ''} onChange={(e) => setF({ ...f, entry_point_id: e.target.value ? Number(e.target.value) : null })}>
            <option value="">— Not linked —</option>
            {scope.modules.flatMap((m) => m.entry_points.map((ep) => <option key={ep.id} value={ep.id}>{m.name} — {ep.name}</option>))}
          </select>
        </Field>
        <label className="row sm" style={{ gap: 8 }}><Switch checked={f.is_active} onChange={(v) => setF({ ...f, is_active: v })} label="Enabled" /> Enabled</label>
        {error && <div className="errt" role="alert">{error}</div>}
      </div>
    </Modal>
  );
}

function Preview({ camera, onClose }: { camera: Camera; onClose: () => void }) {
  const cam = useCamera();
  const [failed, setFailed] = useState(false);
  const browser = camera.type === 'browser';
  useEffect(() => { if (browser) cam.start('user'); return () => cam.stop(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  return (
    <Modal title={`Live preview — ${camera.name}`} wide onClose={onClose} footer={<button className="btn pri" onClick={onClose}>Close</button>}>
      <div className="stage">
        {browser ? <video ref={cam.videoRef} autoPlay playsInline muted style={{ display: cam.running ? 'block' : 'none' }} />
          : !failed && <img src={apiUrl(`/cameras/${camera.id}/stream`)} alt="Live stream" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain' }} onError={() => setFailed(true)} />}
        {(failed || cam.error) && <div style={{ textAlign: 'center', padding: 20 }}><b style={{ color: '#fff', display: 'block' }}>{cam.error?.title ?? 'No video from this camera'}</b><span className="sm">{cam.error?.detail ?? 'The server could not read the stream. Use “Test” for details.'}</span></div>}
      </div>
      <p className="sm mut" style={{ marginTop: 10 }}>{browser ? 'Preview from the camera of the device you are using now.' : 'Relayed by the server as MJPEG. Browsers cannot open RTSP or server-side USB cameras directly.'}</p>
    </Modal>
  );
}

export default function Cameras() {
  const scope = useScope();
  const { can } = useAuth();
  const toast = useToast();
  const manage = can('cameras.manage');
  const list = useApi<Camera[]>(scope.factoryId ? '/cameras' : null, { factory_id: scope.factoryId ?? undefined }, 20000);
  const [form, setForm] = useState<Camera | 'new' | null>(null);
  const [preset, setPreset] = useState<Partial<Camera> | undefined>();
  const [preview, setPreview] = useState<Camera | null>(null);
  const [testing, setTesting] = useState<number | null>(null);
  const [remove, setRemove] = useState<Camera | null>(null);
  const [discovery, setDiscovery] = useState<{ loading: boolean; devices: Device[]; note: string } | null>(null);
  const cams = (list.data ?? []).filter((c) => !scope.moduleId || c.module_id === scope.moduleId);
  const server = cams.filter((c) => c.type !== 'browser');

  async function test(c: Camera) {
    setTesting(c.id);
    try {
      const r = await post<{ ok: boolean; detail: string; resolution: string }>(`/cameras/${c.id}/test`);
      toast.toast(`${c.name}: ${r.detail}${r.resolution ? ` (${r.resolution})` : ''}`, r.ok ? 'ok' : 'bad');
      list.reload();
    } catch (e) { toast.error(e); } finally { setTesting(null); }
  }
  async function discover() {
    setDiscovery({ loading: true, devices: [], note: '' });
    try {
      const r = await post<{ devices: Device[]; note: string }>('/cameras/discover');
      setDiscovery({ loading: false, ...r });
    } catch (e) { toast.error(e); setDiscovery(null); }
  }
  async function confirmRemove() {
    if (!remove) return;
    try { await del(`/cameras/${remove.id}`); toast.ok('Camera removed.'); setRemove(null); list.reload(); } catch (e) { toast.error(e); }
  }

  return (
    <>
      <PageHeader title="Camera management" description="Laptop and mobile cameras run in the browser. USB and IP/RTSP cameras are read by the server and relayed to this page."
        actions={<><button className="btn" disabled={!manage} onClick={discover}><Radar size={16} /> Find ONVIF cameras</button>
          <button className="btn pri" disabled={!manage} onClick={() => { setPreset(undefined); setForm('new'); }}><Plus size={16} /> Add camera</button></>} />
      {list.error && <ErrorBanner message={list.error} onRetry={list.reload} />}
      <div className="g g4">
        <Kpi icon={CameraIcon} label="Cameras configured" value={cams.length} hint={`${cams.filter((c) => c.type === 'browser').length} browser · ${server.length} server-side`} />
        <Kpi icon={CameraIcon} tone="ok" label="Server cameras online" value={`${server.filter((c) => c.status === 'online' && c.is_active).length} / ${server.filter((c) => c.is_active).length}`} hint="Based on the last test or read" />
        <Kpi icon={CameraIcon} tone="bad" label="Offline" value={server.filter((c) => c.status === 'offline' && c.is_active).length} danger={server.some((c) => c.status === 'offline' && c.is_active)} hint="Need attention" />
        <Kpi icon={CameraIcon} tone="info" label="Linked to an entry point" value={cams.filter((c) => c.entry_point_id).length} hint="Used for PPE checks" />
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        {list.loading && !list.data ? <Spinner /> : (
          <div className="tw"><table className="tbl">
            <thead><tr><th>Camera</th><th>Type</th><th>Source</th><th>Entry point</th><th>Status</th><th>Last seen</th><th /></tr></thead>
            <tbody>
              {cams.map((c) => (
                <tr key={c.id}>
                  <td><b>{c.name}</b>{c.resolution && <div className="xs mut">{c.resolution}</div>}</td>
                  <td>{TYPE_LABEL[c.type]}</td>
                  <td className="xs mut" style={{ maxWidth: 240, overflowWrap: 'anywhere' }}>{c.type === 'browser' ? 'Device camera' : c.type === 'usb' ? `Device ${c.source}` : c.source}{c.has_credentials && <div><span className="chip">Credentials stored (encrypted)</span></div>}</td>
                  <td>{c.entry_point ?? <span className="mut">Not linked</span>}</td>
                  <td><CameraStatusChip camera={c} />{c.last_error && c.status === 'offline' && <div className="xs dn" style={{ marginTop: 3, maxWidth: 220 }}>{c.last_error}</div>}</td>
                  <td className="nw">{c.type === 'browser' ? '—' : ago(c.last_seen_at)}</td>
                  <td className="r nw">
                    <button className="btn s" disabled={!manage || testing === c.id || c.type === 'browser'} onClick={() => test(c)}><RefreshCw size={13} className={testing === c.id ? 'spin' : ''} /> {testing === c.id ? 'Testing…' : 'Test'}</button>{' '}
                    <button className="btn s gh icn" aria-label={`Preview ${c.name}`} onClick={() => setPreview(c)}><Eye size={15} /></button>
                    <button className="btn s gh icn" aria-label={`Edit ${c.name}`} disabled={!manage} onClick={() => { setPreset(undefined); setForm(c); }}><Pencil size={15} /></button>
                    <button className="btn s gh icn" aria-label={`Remove ${c.name}`} disabled={!manage} onClick={() => setRemove(c)}><Trash2 size={15} /></button>
                  </td>
                </tr>
              ))}
              {list.data && !cams.length && <tr><td colSpan={7} className="empty">No cameras configured for this selection.</td></tr>}
            </tbody>
          </table></div>
        )}
      </div>
      <div className="note i" style={{ marginTop: 16 }}><Info size={16} /><div>
        <b>How each camera type connects.</b> Laptop webcams and phone cameras are opened by the browser (HTTPS is required outside localhost). USB cameras must be plugged into the machine running the backend. IP cameras are read over RTSP by the backend, which must be on the same network as the cameras — if the application is hosted in the cloud, run an on-site camera gateway. Details: docs/CAMERA_SETUP.md.
      </div></div>

      {form && <CameraForm camera={form === 'new' ? null : form} preset={preset} onClose={() => setForm(null)} onSaved={() => { setForm(null); list.reload(); }} />}
      {preview && <Preview camera={preview} onClose={() => setPreview(null)} />}
      {remove && (
        <Modal title="Remove camera?" onClose={() => setRemove(null)} footer={<><button className="btn" onClick={() => setRemove(null)}>Cancel</button><button className="btn dan" onClick={confirmRemove}>Remove camera</button></>}>
          <p><b>{remove.name}</b> and its stored credentials will be removed. Past entries keep their history.</p>
        </Modal>
      )}
      {discovery && (
        <Modal title="ONVIF camera discovery" onClose={() => setDiscovery(null)} footer={<button className="btn pri" onClick={() => setDiscovery(null)}>Close</button>}>
          {discovery.loading ? <Spinner label="Searching the server’s local network…" /> : (
            <>
              {discovery.devices.map((d) => (
                <div key={d.ip} className="li" style={{ marginBottom: 8 }}>
                  <CameraIcon size={16} /><div className="grow"><div className="b">{d.name}</div><div className="xs mut">{d.ip}</div></div>
                  <button className="btn s" onClick={() => { setDiscovery(null); setPreset({ name: d.name, type: 'onvif', source: `rtsp://${d.ip}:554/` }); setForm('new'); }}>Add</button>
                </div>
              ))}
              {!discovery.devices.length && <div className="empty">No ONVIF devices answered.</div>}
              <p className="sm mut" style={{ marginTop: 10 }}>{discovery.note}</p>
            </>
          )}
        </Modal>
      )}
    </>
  );
}
