import { useEffect, useState } from 'react';
import type { Cloud } from '../../../shared/types.ts';
import type { CloudFile } from '../types.ts';
import { formatBytes } from '../../../shared/validation/uploads.ts';
import { mockAsset } from '../../../mocks/transport.ts';
import Icon from '../../../shared/ui/Icon.tsx';

export default function FileCard({ file, demo, cloud }: { file: CloudFile; demo: boolean; cloud: Cloud }) {
  const [url, setUrl] = useState('');
  const image = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.tipoMime);
  const text = ['text/plain', 'text/markdown', 'text/csv'].includes(file.tipoMime);
  useEffect(() => {
    let objectUrl = '';
    if (demo) {
      const data = mockAsset(localStorage, cloud, file.urlObjeto);
      if (data.startsWith('data:')) {
        const bytes = Uint8Array.from(atob(data.slice(data.indexOf(',') + 1)), char => char.charCodeAt(0));
        objectUrl = URL.createObjectURL(new Blob([bytes], { type: image ? file.tipoMime : text ? 'text/plain' : 'application/octet-stream' }));
        setUrl(objectUrl);
      }
    } else {
      try {
        const parsed = new URL(file.urlObjeto);
        if (parsed.protocol === 'https:' && !parsed.username && !parsed.password) setUrl(parsed.href);
      } catch { /* No renderizar URLs no confiables. */ }
    }
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [file.urlObjeto, file.tipoMime, demo, cloud, image, text]);
  return <article className="file-card">
    <div className={`file-preview ${image ? 'photo' : text ? 'text-preview' : ''}`}>
      {image && url ? <img src={url} alt={`Vista previa de ${file.nombreOriginal}`} loading="lazy" /> : <><Icon name={image ? 'image' : 'file'} size={36} /><span>{text ? 'TEXTO' : file.nombreOriginal.split('.').pop()?.toUpperCase() || 'ARCHIVO'}</span></>}
    </div>
    <div className="file-info">
      <h3 title={file.nombreOriginal}>{file.nombreOriginal}</h3><p>{file.tipoMime}</p>
      <div className="file-details"><span>{formatBytes(file.tamanoBytes)}</span><span>{file.proveedorAlmacenamiento}</span></div>
      {url ? <a className="file-open" href={url} target="_blank" rel="noopener noreferrer" download={demo && !image && !text ? file.nombreOriginal : undefined}>{demo && !image && !text ? 'Descargar archivo' : 'Abrir archivo'}<Icon name="external" size={15} /></a> : <span className="muted">URL no disponible</span>}
    </div>
  </article>;
}
