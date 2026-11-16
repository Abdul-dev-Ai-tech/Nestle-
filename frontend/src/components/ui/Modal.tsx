import { X } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';

export function Modal({ title, children, footer, onClose, wide }: {
  title: ReactNode; children: ReactNode; footer?: ReactNode; onClose: () => void; wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);
  return (
    <div className="ov" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? 'w' : ''}`} role="dialog" aria-modal="true">
        <div className="mh"><h2>{title}</h2><button className="btn gh s icn" onClick={onClose} aria-label="Close"><X size={18} /></button></div>
        <div className="mb">{children}</div>
        {footer && <div className="mf">{footer}</div>}
      </div>
    </div>
  );
}
