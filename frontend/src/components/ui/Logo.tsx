import logo from '@/assets/nestle-logo.png';

/** Authorized Nestlé logo supplied by the project owner (frontend/src/assets/nestle-logo.png). */
export function Logo({ className = '' }: { className?: string }) {
  return <span className={`mark logo ${className}`}><img src={logo} alt="Nestlé" /></span>;
}
export const logoUrl = logo;
