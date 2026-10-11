import { useState } from 'react';
import type { Api } from '../../../lib/api/index.ts';
import type { Task, TaskChange } from '../types.ts';
import { useTasks } from '../hooks.ts';
import TaskCard from '../components/TaskCard.tsx';
import TaskEditor from '../components/TaskEditor.tsx';
import { Modal } from '../../../shared/ui/Modal.tsx';
import Icon from '../../../shared/ui/Icon.tsx';

type Props = { api: Api; token: string; scope: string; notify: (text: string) => void };
export default function TasksPage({ api, token, scope, notify }: Props) {
  const { query, mutation } = useTasks(api, token, scope);
  const tasks = query.data?.tareas || [];
  const busy = mutation.isPending;
  const error = mutation.error?.message || query.error?.message || '';
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<Task | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Task | null>(null);
  async function mutate(change: TaskChange, success: () => void) {
    if (busy) return;
    try { await mutation.mutateAsync(change); success(); }
    catch { /* TanStack Query conserva el error para mostrarlo. */ }
  }
  function openEditor(task: Task | 'new') { mutation.reset(); setEditing(task); }
  const completed = tasks.filter(task => task.completada).length;
  const visible = tasks.filter(task => (filter === 'all' || task.completada === (filter === 'done'))
    && `${task.titulo} ${task.descripcion}`.toLowerCase().includes(search.toLowerCase()));
  return <>
    <section className="page-intro">
      <div><h1>Mis tareas</h1><p>Crea, organiza y completa tus pendientes.</p></div>
      <button className="button primary" onClick={() => openEditor('new')} disabled={query.isPending || busy}><Icon name="plus" /> Nueva tarea</button>
    </section>
    <section className="stats-grid" aria-label="Resumen de tareas">
      <div className="stat"><span className="stat-icon peach"><Icon name="tasks" /></span><div><small>En tu espacio</small><strong>{tasks.length}<span>tareas</span></strong></div></div>
      <div className="stat"><span className="stat-icon sand"><Icon name="clock" /></span><div><small>Por hacer</small><strong>{tasks.length - completed}<span>pendientes</span></strong></div></div>
      <div className="stat"><span className="stat-icon sage"><Icon name="check" /></span><div><small>Completadas</small><strong>{completed}<span>completadas</span></strong></div></div>
    </section>
    <section className="workspace-section">
      <div className="section-heading"><div><h2>Listado <span className="count">{tasks.length}</span></h2><p>Busca una tarea o filtra por su estado.</p></div></div>
      <div className="toolbar">
        <div className="filter-tabs" aria-label="Filtrar tareas">{[['all', 'Todas'], ['pending', 'Pendientes'], ['done', 'Completadas']].map(([value, title]) => <button key={value} className={filter === value ? 'active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{title}</button>)}</div>
        <label className="search"><Icon name="search" size={18} /><input aria-label="Buscar tareas" placeholder="Buscar una tarea…" value={search} onChange={event => setSearch(event.target.value)} /></label>
      </div>
      {error && <div role="alert" className="error-box">{error} <button className="text-button" onClick={() => { mutation.reset(); void query.refetch(); }}>Volver a cargar</button></div>}
      {query.isPending ? <div className="loading-state" role="status">Cargando tu espacio…</div> : visible.length ? <div className="task-grid">
        {visible.map(task => <TaskCard key={task.id} task={task} busy={busy}
          onToggle={() => void mutate({ kind: 'complete', id: task.id, completada: !task.completada }, () => notify(task.completada ? 'Tarea marcada como pendiente.' : '¡Un paso más! Tarea completada.'))}
          onEdit={() => openEditor(task)} onDelete={() => { mutation.reset(); setDeleting(task); }} />)}
        <button className="add-card" onClick={() => openEditor('new')} disabled={busy}><span><Icon name="plus" size={20} /></span>Agregar otra tarea</button>
      </div> : <div className="empty-state"><span className="empty-icon"><Icon name="tasks" size={30} /></span><h3>{search || filter !== 'all' ? 'Nada por aquí, por ahora.' : 'Tu próxima idea tiene lugar aquí.'}</h3><p>{search || filter !== 'all' ? 'Prueba otra búsqueda o cambia el filtro.' : 'Crea una tarea y empieza a avanzar.'}</p>{!search && filter === 'all' && <button className="button primary" onClick={() => openEditor('new')}><Icon name="plus" /> Crear primera tarea</button>}</div>}
    </section>
    {editing && <TaskEditor task={editing} busy={busy} error={error}
      onClose={() => { if (!busy) setEditing(null); }}
      onSave={input => void mutate(editing === 'new' ? { kind: 'create', input } : { kind: 'edit', id: editing.id, input }, () => { setEditing(null); notify('Tarea guardada. Sigue a tu ritmo.'); })} />}
    {deleting && <Modal title="¿Eliminar esta tarea?" onClose={() => { if (!busy) setDeleting(null); }}>
      <p className="muted">«{deleting.titulo}» se eliminará. Esta acción no se puede deshacer.</p>
      {error && <div className="error-box" role="alert">{error}</div>}
      <div className="modal-actions"><button className="button outline" disabled={busy} onClick={() => setDeleting(null)}>Conservar</button><button className="button destructive" disabled={busy} onClick={() => void mutate({ kind: 'delete', id: deleting.id }, () => { setDeleting(null); notify('Tarea eliminada.'); })}>{busy ? 'Eliminando…' : 'Sí, eliminar'}</button></div>
    </Modal>}
  </>;
}
