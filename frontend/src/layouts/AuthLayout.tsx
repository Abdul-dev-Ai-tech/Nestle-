import { DoorOpen, FileCheck, ScanLine, Check, Unlock } from 'lucide-react';
import type { ReactNode } from 'react';
import { Logo, logoUrl } from '@/components/ui/Logo';
import { PPE_ITEMS, PPE_LABELS } from '@/types';

/** Split sign-in layout: brand panel on the left, form card on the right. */
export default function AuthLayout({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return (
    <div className="auth">
      <section className="hero">
        <div className="row"><Logo /></div>
        <div>
          <h2 style={{ marginTop: 4 }}>Only compliant personnel enter production.</h2>
          <p style={{ color: '#D5C8B4', maxWidth: 460, marginTop: 12 }}>
            AI-powered PPE verification at every entry point, linked to smart door access, with audit-ready evidence for each violation.
          </p>
          <div className="livecard" aria-hidden="true">
            <div className="hd"><span>Entry check · illustration</span><span>Gate A</span></div>
            <div className="sl" />
            {PPE_ITEMS.map((i) => <div className="rw" key={i}><span className="ck"><Check size={13} /></span>{PPE_LABELS[i]}</div>)}
            <div className="ps"><Unlock size={15} /> PASS — door unlocked</div>
          </div>
        </div>
        <div className="ft">
          <div><ScanLine size={20} /><b>PPE verification</b>Uniform, hair cap, mask, beard net, safety shoes</div>
          <div><DoorOpen size={20} /><b>Smart access</b>Door opens automatically on PASS</div>
          <div><FileCheck size={20} /><b>Audit ready</b>Image evidence and full history</div>
        </div>
      </section>
      <section className="af">
        <div className="afb">
          <div className="row" style={{ marginBottom: 24 }}><img className="authlogo" src={logoUrl} alt="Nestlé" /></div>
          <h1>{title}</h1>
          <p className="mut" style={{ margin: '6px 0 20px' }}>{subtitle}</p>
          {children}
          <p className="xs mut" style={{ marginTop: 26 }}>Authorized personnel only. All activity is logged.</p>
        </div>
      </section>
    </div>
  );
}
