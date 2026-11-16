import { ChevronLeft, ChevronRight, LayoutDashboard } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { PAGES, pageFor } from '@/utils/nav';

/** Breadcrumbs + title + description + primary action. Used by every page for consistency. */
export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  const page = pageFor(useLocation().pathname);
  return (
    <>
      {page && (
        <nav className="crumbs" aria-label="Breadcrumb">
          <LayoutDashboard size={13} /><span>Home</span><ChevronRight size={12} /><span>{page.group}</span>
          <ChevronRight size={12} /><b>{page.label}</b>
          <span className="stp">Step {PAGES.indexOf(page) + 1} of {PAGES.length}</span>
        </nav>
      )}
      <div className="ph">
        <div><h1>{title}</h1>{description && <p>{description}</p>}</div>
        {actions && <div className="row wrap">{actions}</div>}
      </div>
    </>
  );
}

/** Previous / next step links, limited to pages the user may open. */
export function StepNav() {
  const { can } = useAuth();
  const page = pageFor(useLocation().pathname);
  if (!page) return null;
  const allowed = PAGES.filter((p) => can(p.permission));
  const i = allowed.indexOf(page);
  const prev = allowed[i - 1];
  const next = allowed[i + 1];
  return (
    <div className="pnav">
      {prev ? <Link to={prev.path}><ChevronLeft size={16} /><span><small>Previous</small>{prev.label}</span></Link> : <span />}
      {next && <Link className="nx" to={next.path}><span><small>Next step</small>{next.label}</span><ChevronRight size={16} /></Link>}
    </div>
  );
}
