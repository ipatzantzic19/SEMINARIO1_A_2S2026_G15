import type { Task } from '../types.ts';
import Icon from '../../../shared/ui/Icon.tsx';

type Props = { task: Task; busy: boolean; onToggle: () => void; onEdit: () => void; onDelete: () => void };
export default function TaskCard({ task, busy, onToggle, onEdit, onDelete }: Props) {
  return <article className={`task-card ${task.completada ? 'completed' : ''}`}>
    <div className="task-top">
      <span className={`status-pill ${task.completada ? 'done' : ''}`}><i />{task.completada ? 'Completada' : 'Por hacer'}</span>
      <button className={`check-button ${task.completada ? 'checked' : ''}`} aria-label={`${task.completada ? 'Marcar pendiente' : 'Completar'}: ${task.titulo}`} aria-pressed={task.completada} disabled={busy} onClick={onToggle}><Icon name="check" size={17} /></button>
    </div>
    <h3>{task.titulo}</h3><p>{task.descripcion || 'Sin descripción.'}</p>
    <div className="task-footer">
      <span><Icon name="clock" size={14} />{new Date(task.fechaCreacion).toLocaleDateString('es-GT', { day: 'numeric', month: 'short' })}</span>
      <div><button className="icon-button" aria-label={`Editar: ${task.titulo}`} onClick={onEdit} disabled={busy}><Icon name="edit" size={17} /></button><button className="icon-button danger" aria-label={`Eliminar: ${task.titulo}`} onClick={onDelete} disabled={busy}><Icon name="trash" size={17} /></button></div>
    </div>
  </article>;
}
