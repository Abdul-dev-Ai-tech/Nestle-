import { useEffect, useMemo, useState } from 'react';
import { logoUrl } from './Logo';

const STEPS = ['Starting secure workspace', 'Loading factory modules', 'Connecting camera services', 'Preparing compliance dashboard', 'Ready'];

/** Branded loading screen: logo reveal, animated progress, fade into the app. */
export function Splash({ duration = 2600, onDone }: { duration?: number; onDone: () => void }) {
  const [pct, setPct] = useState(0);
  const [leaving, setLeaving] = useState(false);
  const particles = useMemo(() => Array.from({ length: 18 }, (_, i) => ({
    id: i, x: Math.random() * 100, s: 2 + Math.random() * 4, d: 5 + Math.random() * 6, dl: -Math.random() * 8,
  })), []);

  useEffect(() => {
    const start = performance.now();
    const timer = window.setInterval(() => {
      const k = Math.min(1, (performance.now() - start) / duration);
      setPct(Math.round((1 - (1 - k) ** 2) * 100));
      if (k >= 1) {
        window.clearInterval(timer);
        setLeaving(true);
        window.setTimeout(onDone, 720);
      }
    }, 60);
    return () => window.clearInterval(timer);
  }, [duration, onDone]);

  return (
    <div className={`splash ${leaving ? 'out' : ''}`} role="status" aria-label="Loading">
      <span className="orb" /><span className="orb o2" />
      {particles.map((p) => (
        <i key={p.id} className="pt" style={{ ['--x' as string]: `${p.x}%`, ['--s' as string]: `${p.s}px`, ['--d' as string]: `${p.d}s`, ['--dl' as string]: `${p.dl}s` }} />
      ))}
      <div className="bx">
        <div className="splogo has"><img src={logoUrl} alt="Nestlé" /></div>
        <p className="tg">AI Personnel Entry Compliance &amp; Smart Access Control</p>
        <div className="ld">
          <div className="pbar"><i style={{ width: `${pct}%` }} /></div>
          <div className="st"><span>{STEPS[Math.min(STEPS.length - 1, Math.floor((pct / 100) * STEPS.length))]}</span><span>{pct}%</span></div>
        </div>
      </div>
    </div>
  );
}
