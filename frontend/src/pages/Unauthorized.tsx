import { Lock } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { PAGES, pageFor } from '@/utils/nav';

export default function Unauthorized() {
  const { me, can } = useAuth();
  const page = pageFor(useLocation().pathname);
  const home = PAGES.find((p) => can(p.permission));
  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '62vh' }}>
      <div className="card" style={{ maxWidth: 480, textAlign: 'center' }}>
        <div className="cb" style={{ padding: '34px 28px' }}>
          <div style={{ width: 68, height: 68, borderRadius: 20, background: 'var(--failbg)', color: 'var(--fail)', display: 'grid', placeItems: 'center', margin: '0 auto 14px' }}><Lock size={30} /></div>
          <div className="xs b mut" style={{ letterSpacing: '.1em' }}>ERROR 403</div>
          <h1 style={{ margin: '6px 0' }}>Access restricted</h1>
          <p className="mut">Your role (<b>{me?.user.role}</b>) does not have permission to open <b>{page?.label ?? 'this page'}</b>.</p>
          <div className="row wrap" style={{ justifyContent: 'center', marginTop: 16 }}>
            <Link className="btn pri" to={home ? home.path : '/profile'}>Back to {home ? home.label : 'my profile'}</Link>
          </div>
          <p className="xs mut" style={{ marginTop: 14 }}>Need access? Contact your Factory Admin.</p>
        </div>
      </div>
    </div>
  );
}
