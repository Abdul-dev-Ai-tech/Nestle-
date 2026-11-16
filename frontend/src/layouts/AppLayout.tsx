import { Bell, ChevronDown, ChevronRight, Clock, Lock, LogOut, Menu, User as UserIcon } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Logo } from '@/components/ui/Logo';
import { SeverityChip } from '@/components/ui/basic';
import { StepNav } from '@/components/ui/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useScope } from '@/contexts/ScopeContext';
import { useToast } from '@/contexts/ToastContext';
import { useApi } from '@/hooks/useApi';
import { useClock } from '@/hooks/useClock';
import type { Alert, Page } from '@/types';
import { ago, avatarStyle, initials } from '@/utils/format';
import { PAGES, pageFor } from '@/utils/nav';

type AlertList = Page<Alert> & { unread: number; unacknowledged: number };

function ClockPill() {
  const now = useClock();
  return (
    <span className="clock hide-t">
      <Clock size={15} />
      {now.toLocaleDateString([], { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })} ·{' '}
      <b>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</b>
    </span>
  );
}

export default function AppLayout() {
  const { me, can, logout } = useAuth();
  const scope = useScope();
  const toast = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const [drawer, setDrawer] = useState(false);
  const [menu, setMenu] = useState<'bell' | 'user' | null>(null);
  const [ringing, setRinging] = useState(false);
  const menus = useRef<HTMLDivElement>(null);
  const page = pageFor(location.pathname);
  const alerts = useApi<AlertList>(can('alerts.view') && scope.factoryId ? '/alerts' : null,
    { factory_id: scope.factoryId ?? undefined, page_size: 5 }, 15000);
  const unread = alerts.data?.unread ?? 0;
  const lastUnread = useRef(0);

  useEffect(() => { setDrawer(false); setMenu(null); window.scrollTo(0, 0); }, [location.pathname]);
  useEffect(() => {
    if (unread > lastUnread.current && lastUnread.current !== 0) { setRinging(true); window.setTimeout(() => setRinging(false), 1000); }
    lastUnread.current = unread;
  }, [unread]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (menus.current && !menus.current.contains(e.target as Node)) setMenu(null); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  if (!me) return null;
  const user = me.user;
  let group = '';

  async function signOut() {
    await logout();
    toast.toast('You have been signed out.');
    navigate('/login', { replace: true });
  }

  return (
    <div className="app">
      <aside className={`side ${drawer ? 'open' : ''}`} id="side">
        <div className="brand haslogo"><Logo /><div><small>AI Entry Compliance · Smart Access Control</small></div></div>
        <nav className="nav" aria-label="Main navigation">
          {PAGES.map((p, i) => {
            const allowed = can(p.permission);
            const heading = p.group !== group ? (group = p.group) : null;
            const Icon = allowed ? p.icon : Lock;
            return (
              <div key={p.path}>
                {heading && <h6>{heading}</h6>}
                <NavLink to={p.path} className={({ isActive }) => `${isActive ? 'on' : ''} ${allowed ? '' : 'lk'}`}>
                  <span className="ni"><Icon size={16} /></span><span>{p.label}</span>
                  {p.path === '/violations' && allowed && unread > 0
                    ? <span className="bdg">{unread}</span>
                    : <span className="no">{String(i + 1).padStart(2, '0')}</span>}
                </NavLink>
              </div>
            );
          })}
        </nav>
        <Link to="/profile" className="sideu" style={{ textDecoration: 'none' }}>
          <span className="av" style={avatarStyle(user.full_name)}>{initials(user.full_name)}</span>
          <div className="grow"><b>{user.full_name}</b><small>{user.role}</small></div><ChevronRight size={14} />
        </Link>
        <div className="sidef">{scope.factory ? `${scope.factory.name} · ${scope.factory.code}` : '—'}<br />Environment: {me.environment}</div>
      </aside>
      {drawer && <div className="scrim" onClick={() => setDrawer(false)} />}

      <div className="main">
        <header className="top">
          <button className="btn gh icn hide-d" onClick={() => setDrawer((d) => !d)} aria-label="Open menu"><Menu size={20} /></button>
          <div className="grow">
            <div className="ttl">{page?.label ?? (location.pathname === '/profile' ? 'My Profile' : 'Access restricted')}</div>
            <div className="sub hide-m">{page?.desc ?? ''}</div>
          </div>
          <ClockPill />
          {scope.factories.length > 1 && (
            <select className="in hide-m" style={{ width: 'auto', maxWidth: 190, height: 36, fontWeight: 600 }} aria-label="Factory"
              value={scope.factoryId ?? ''} onChange={(e) => scope.setFactoryId(Number(e.target.value))}>
              {scope.factories.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          )}
          <select className="in" style={{ width: 'auto', maxWidth: 170, height: 36, fontWeight: 600 }} aria-label="Factory module filter"
            value={scope.moduleId ?? 'all'} onChange={(e) => scope.setModuleId(e.target.value === 'all' ? null : Number(e.target.value))}>
            <option value="all">All modules</option>
            {scope.modules.filter((m) => m.is_active).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <div ref={menus} className="row" style={{ gap: 4 }}>
            {can('alerts.view') && (
              <div className="rel">
                <button className={`btn gh icn bell ${ringing ? 'ringing' : ''}`} aria-label="Notifications" onClick={() => setMenu(menu === 'bell' ? null : 'bell')}>
                  <Bell size={20} />{unread > 0 && <i>{unread > 9 ? '9+' : unread}</i>}
                </button>
                {menu === 'bell' && (
                  <div className="pop">
                    <div className="row sp" style={{ padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
                      <b>Alerts</b><span className={`chip ${unread ? 'bad' : ''}`}>{unread} unread</span>
                    </div>
                    {(alerts.data?.items ?? []).map((a) => (
                      <Link key={a.id} className="mi" to="/violations?tab=alerts" onClick={() => setMenu(null)}>
                        <SeverityChip severity={a.severity} />
                        <div className="grow"><div className="b sm">{a.title}</div><div className="xs mut">{ago(a.created_at)}</div></div>
                      </Link>
                    ))}
                    {!alerts.data?.items.length && <div className="empty sm">No alerts.</div>}
                    <Link className="mi b sm" to="/violations?tab=alerts" onClick={() => setMenu(null)} style={{ justifyContent: 'center', borderTop: '1px solid var(--line)' }}>Open alert center</Link>
                  </div>
                )}
              </div>
            )}
            <div className="rel">
              <button className="btn gh" style={{ padding: '0 6px' }} aria-label="Account" onClick={() => setMenu(menu === 'user' ? null : 'user')}>
                <span className="av" style={avatarStyle(user.full_name)}>{initials(user.full_name)}</span><span className="hide-m"><ChevronDown size={14} /></span>
              </button>
              {menu === 'user' && (
                <div className="pop" style={{ width: 250 }}>
                  <div style={{ padding: 14, borderBottom: '1px solid var(--line)' }}>
                    <div className="b">{user.full_name}</div><div className="xs mut">{user.email}</div>
                    <div style={{ marginTop: 6 }}><span className="chip info">{user.role}</span></div>
                  </div>
                  <Link className="mi" to="/profile" onClick={() => setMenu(null)}><UserIcon size={16} /> My profile</Link>
                  <button className="mi" style={{ color: 'var(--fail)', borderTop: '1px solid var(--line)', width: '100%', background: 'none', border: 0, borderTopWidth: 1, borderTopStyle: 'solid', borderTopColor: 'var(--line)', font: 'inherit' }} onClick={signOut}>
                    <LogOut size={16} /> Log out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="view anim" key={location.pathname}>
          <Outlet />
          <StepNav />
        </main>
      </div>
    </div>
  );
}
