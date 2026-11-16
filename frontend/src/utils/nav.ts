import { AlertTriangle, BarChart3, Camera, DoorOpen, Factory, LayoutDashboard, ScanFace, Settings, ShieldCheck, Users, type LucideIcon } from 'lucide-react';

export interface NavPage { path: string; label: string; group: string; desc: string; icon: LucideIcon; permission: string }

/** Sequential navigation — the order users are expected to move through the product. */
export const PAGES: NavPage[] = [
  { path: '/dashboard', label: 'Overview Dashboard', group: 'Monitor', desc: 'Today at a glance', icon: LayoutDashboard, permission: 'dashboard.view' },
  { path: '/monitoring', label: 'Live AI Monitoring', group: 'Monitor', desc: 'Camera preview and PPE checks', icon: ScanFace, permission: 'monitoring.view' },
  { path: '/employees', label: 'Employee Management', group: 'Operations', desc: 'People allowed to request entry', icon: Users, permission: 'employees.view' },
  { path: '/modules', label: 'Factory Modules', group: 'Operations', desc: 'Areas, entry points and PPE rules', icon: Factory, permission: 'modules.view' },
  { path: '/cameras', label: 'Camera Management', group: 'Operations', desc: 'Webcams, USB and IP cameras', icon: Camera, permission: 'cameras.view' },
  { path: '/access', label: 'Smart Access Control', group: 'Operations', desc: 'Doors, overrides and entry history', icon: DoorOpen, permission: 'access.view' },
  { path: '/violations', label: 'Violations & Alerts', group: 'Operations', desc: 'Failed checks and notifications', icon: AlertTriangle, permission: 'violations.view' },
  { path: '/reports', label: 'Reports & Analytics', group: 'Insights', desc: 'Compliance history and audit logs', icon: BarChart3, permission: 'reports.view' },
  { path: '/users', label: 'User Management', group: 'Administration', desc: 'System users, roles and permissions', icon: ShieldCheck, permission: 'users.view' },
  { path: '/settings', label: 'System Settings', group: 'Administration', desc: 'Factory, rules and devices', icon: Settings, permission: 'settings.view' },
];

export const pageFor = (pathname: string) => PAGES.find((p) => pathname === p.path || pathname.startsWith(p.path + '/'));
