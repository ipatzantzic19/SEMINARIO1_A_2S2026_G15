import { useRef, useState } from 'react';
import type { Api } from '../../../lib/api/index.ts';
import type { Cloud } from '../../../shared/types.ts';
import { formatBytes } from '../../../shared/validation/uploads.ts';
import { useFiles, useFileUpload } from '../hooks.ts';
import FileCard from '../components/FileCard.tsx';
import Icon from '../../../shared/ui/Icon.tsx';

type Props = { api: Api; token: string; userId: number; cloud: Cloud; demo: boolean; scope: string; notify: (text: string) => void };
export default function DrivePage({ api, token, userId, cloud, demo, scope, notify }: Props) {
  const query = useFiles(api, token, scope);
  const { mutation, pending, status } = useFileUpload(api, token, scope, userId);
  const files = query.data?.archivos || [];
  const busy = mutation.isPending;
  const [localError, setError] = useState('');
  const error = localError || mutation.error?.message || query.error?.message || '';
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  async function upload(file?: File) {
    if (!file || busy || pending) return;
    setError('');
    try { await mutation.mutateAsync(file); notify('Archivo guardado. Ya está en tu CloudDrive.'); }
    catch { /* TanStack Query conserva el error para mostrarlo. */ }
    finally { if (input.current) input.current.value = ''; }
  }
  async function retry() {
    if (!pending || busy) return;
    setError('');
    try { await mutation.mutateAsync(null); notify('Archivo guardado. Ya está en tu CloudDrive.'); }
    catch { /* No repetir la carga: conservar metadatos pendientes. */ }
  }
  const visible = files.filter(file => file.nombreOriginal.toLowerCase().includes(search.toLowerCase())
    && (filter === 'all' || (filter === 'image' ? file.tipoMime.startsWith('image/') : file.tipoMime.startsWith('text/'))));
  return <>
    <section className="page-intro">
      <div><span className="eyebrow">TODO A MANO</span><h1>Un lugar para tus archivos<span>.</span></h1><p>Guarda lo que necesitas. Encuéntralo cuando importa.</p></div>
      <span className="storage-label"><Icon name="cloud" />{cloud === 'aws' ? 'Amazon S3' : 'Azure Blob'}{demo && ' · simulado'}</span>
    </section>
    <section className={`upload-zone ${dragging ? 'dragging' : ''}`} aria-label="Cargar archivo"
      onDragOver={event => { event.preventDefault(); if (!busy && !pending) setDragging(true); }} onDragLeave={() => setDragging(false)}
      onDrop={event => { event.preventDefault(); setDragging(false); if (event.dataTransfer.files.length > 1) { setError('Selecciona un archivo a la vez.'); return; } void upload(event.dataTransfer.files[0]); }}>
      <span className="upload-icon"><Icon name="upload" size={28} /></span><h2>{status || 'Dale un lugar a ese archivo'}</h2><p>Arrástralo aquí o selecciónalo desde tu dispositivo.</p>
      <input ref={input} type="file" id="drive-upload" className="visually-hidden" aria-label="Seleccionar archivo para CloudDrive" disabled={busy || !!pending} onChange={event => void upload(event.target.files?.[0])} />
      <button className="button primary" disabled={busy || !!pending} onClick={() => input.current?.click()}><Icon name="plus" size={17} />{busy ? 'Guardando…' : 'Seleccionar archivo'}</button>
      <small>Imágenes y otros archivos: 3 MiB · Texto UTF-8: 1 MiB · Sin ejecutables, HTML o SVG.</small>{busy && <span role="status" className="upload-status">{status}</span>}
    </section>
    {error && <div className="error-box" role="alert">{error}</div>}
    {pending && !busy && <div className="pending-upload"><Icon name="clock" /><div><strong>La carga está hecha; falta registrar el archivo.</strong><p>{pending.nombreOriginal} · Reintentaremos solo los metadatos, sin volver a subirlo.</p></div><button className="button outline" onClick={retry}>Reintentar registro</button></div>}
    <section className="workspace-section">
      <div className="section-heading"><div><h2>Mis archivos <span className="count">{files.length}</span></h2><p>{formatBytes(files.reduce((sum, file) => sum + file.tamanoBytes, 0))} en tu espacio{demo ? ' de demostración' : ''}.</p></div><button className="text-button" disabled={busy || query.isFetching} onClick={() => void query.refetch()}>Actualizar</button></div>
      <div className="toolbar">
        <div className="filter-tabs" aria-label="Filtrar archivos">{[['all', 'Todos'], ['image', 'Imágenes'], ['text', 'Textos']].map(([value, title]) => <button key={value} className={filter === value ? 'active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{title}</button>)}</div>
        <label className="search"><Icon name="search" size={18} /><input aria-label="Buscar archivos" placeholder="Buscar un archivo…" value={search} onChange={event => setSearch(event.target.value)} /></label>
      </div>
      {query.isPending ? <div className="loading-state" role="status">Cargando tus archivos…</div> : visible.length ? <div className="file-grid">{visible.map(file => <FileCard key={file.id} file={file} demo={demo} cloud={cloud} />)}</div> : <div className="empty-state"><span className="empty-icon"><Icon name="cloud" size={34} /></span><h3>{search || filter !== 'all' ? 'No encontramos archivos con ese filtro.' : 'Lo importante merece su espacio.'}</h3><p>{search || filter !== 'all' ? 'Prueba otra búsqueda.' : 'Carga tu primer archivo. Lo tendrás siempre a mano.'}</p></div>}
    </section>
  </>;
}
