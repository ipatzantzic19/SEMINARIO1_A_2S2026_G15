import { useState } from 'react';
import type { FormEvent } from 'react';
import type { Task, TaskInput } from '../types.ts';
import { taskInputSchema } from '../schemas.ts';
import { validateForm } from '../../../shared/validation/schema.ts';
import { Modal } from '../../../shared/ui/Modal.tsx';
import Icon from '../../../shared/ui/Icon.tsx';

type Props = { task: Task | 'new'; busy: boolean; error: string; onClose: () => void; onSave: (input: TaskInput) => void };
export default function TaskEditor({ task, busy, error, onClose, onSave }: Props) {
  const [formError, setFormError] = useState('');
  const isNew = task === 'new';
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      setFormError('');
      const input: TaskInput = { titulo: String(data.get('title')), descripcion: String(data.get('description')).trim() };
      if (isNew) {
        const date = new Date(String(data.get('date')));
        if (!Number.isFinite(date.getTime())) throw new Error('Ingresa una fecha de creación válida.');
        input.fechaCreacion = date.toISOString();
      }
      onSave(validateForm(taskInputSchema, input));
    } catch (cause) { setFormError(cause instanceof Error ? cause.message : 'Revisa los datos.'); }
  }
  const localNow = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  return <Modal title={isNew ? 'Una nueva tarea' : 'Editar tarea'} onClose={onClose}>
    <p className="muted">Dale un nombre. El primer paso ya está hecho.</p>
    {(formError || error) && <div className="error-box" role="alert">{formError || error}</div>}
    <form onSubmit={submit}><fieldset className="form-fields" disabled={busy}>
      <label>Título<input name="title" autoFocus required maxLength={200} pattern=".*\S.*" defaultValue={isNew ? '' : task.titulo} placeholder="¿Qué te gustaría hacer?" /></label>
      <label>Descripción<textarea name="description" rows={4} defaultValue={isNew ? '' : task.descripcion} placeholder="Un poco de contexto, si lo necesitas…" /></label>
      {isNew && <label>Fecha de creación<input name="date" type="datetime-local" required defaultValue={localNow} /></label>}
      <div className="modal-actions"><button className="button outline" type="button" onClick={onClose}>Cancelar</button><button className="button primary" type="submit">{busy ? 'Guardando…' : 'Guardar tarea'}<Icon name="check" size={18} /></button></div>
    </fieldset></form>
  </Modal>;
}
