import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '62vh' }}>
      <div className="card" style={{ maxWidth: 460, textAlign: 'center' }}>
        <div className="cb" style={{ padding: '34px 28px' }}>
          <div className="mut"><Compass size={34} /></div>
          <div className="xs b mut" style={{ letterSpacing: '.1em', marginTop: 8 }}>ERROR 404</div>
          <h1 style={{ margin: '6px 0' }}>Page not found</h1>
          <p className="mut">This address does not match any page in the application.</p>
          <Link className="btn pri" style={{ marginTop: 16 }} to="/">Go to the start page</Link>
        </div>
      </div>
    </div>
  );
}
