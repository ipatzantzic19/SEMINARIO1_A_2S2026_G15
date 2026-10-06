import { useEffect, useId, useRef } from 'react';
import type { ReactNode } from 'react';
import Icon from './Icon.tsx';

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    const opener = document.activeElement;
    dialog.showModal();
    return () => {
      dialog.close();
      if (opener instanceof dialog.ownerDocument.defaultView!.HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);
  return <dialog ref={ref} className="modal" aria-labelledby={titleId} onCancel={event => {
    event.preventDefault(); onClose();
  }}><div className="modal-heading"><h2 id={titleId}>{title}</h2><button type="button" className="icon-button" aria-label="Cerrar diálogo" onClick={onClose}><Icon name="close" /></button></div>{children}</dialog>;
}
