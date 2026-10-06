import { useCallback, useEffect, useMemo, useState } from 'react';
import { useStore } from 'zustand';
import { useQueryClient } from '@tanstack/react-query';
import type { Cloud } from '../shared/types.ts';
import type { LoginResult, Session } from '../features/auth/types.ts';
import { assertCloudReady, loadConfig } from '../config/env.ts';
import type { Config } from '../config/env.ts';
import { createApi } from '../lib/api/index.ts';
import { createMockTransport, mockAsset } from '../mocks/transport.ts';
import { createAuthStore } from '../features/auth/auth.store.ts';
import Auth from '../features/auth/pages/AuthPage.tsx';
import Tasks from '../features/tasks/pages/TasksPage.tsx';
import Drive from '../features/files/pages/DrivePage.tsx';
import Icon from '../shared/ui/Icon.tsx';

export default function App() {
  let config: Config;
  try { config = loadConfig(import.meta.env || {}, window.TASKFLOW_CONFIG); }
  catch (error) { return <main className="config-error"><h1>Revisemos la configuración.</h1><p role="alert">{error instanceof Error ? error.message : 'Configuración inválida.'}</p><p>Edita el archivo público config.js y vuelve a cargar la página.</p></main>; }
  return <Workspace config={config} />;
}

function Workspace({ config }: { config: Config }) {
  const [cloud, setCloud] = useState<Cloud>(config.defaultCloud);
  const keyFor = (provider: Cloud) => `taskflow-session:${config.mode}:${provider}:${config[provider].apiBaseUrl}:${config[provider].uploadBaseUrl}`;
  const key = keyFor(cloud);
  const [authStore] = useState(() => createAuthStore(sessionStorage, key));
  const session = useStore(authStore, state => state.session);
  const authEpoch = useStore(authStore, state => state.epoch);
  const queryClient = useQueryClient();
  const [page, setPage] = useState<'tasks' | 'drive'>('tasks');
  const [notice, setNotice] = useState('');
  const logout = useCallback(() => {
    if (authStore.getState().scope !== key) return;
    void queryClient.cancelQueries(); queryClient.clear();
    authStore.getState().clearSession(key); setPage('tasks');
  }, [authStore, key, queryClient]);
  const unauthorized = useCallback((token: string) => {
    if (authStore.getState().scope !== key || authStore.getState().session?.token !== token) return;
    logout(); setNotice('Tu sesión expiró. Inicia sesión nuevamente.');
  }, [logout, key, authStore]);
  const apiBaseUrl = config[cloud].apiBaseUrl;
  const uploadBaseUrl = config[cloud].uploadBaseUrl;
  const api = useMemo(() => createApi(apiBaseUrl, uploadBaseUrl,
    config.mode === 'mock' ? createMockTransport(localStorage, cloud) : undefined, unauthorized, config.timeoutMs),
  [cloud, config.mode, config.timeoutMs, apiBaseUrl, uploadBaseUrl, unauthorized]);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 6000); return () => clearTimeout(timer); }, [notice]);
  useEffect(() => {
    if (!session) return;
    const timer = setTimeout(() => unauthorized(session.token), Math.max(0, session.expiresAt - Date.now()));
    return () => clearTimeout(timer);
  }, [session, unauthorized]);
  function login(result: LoginResult) {
    if (authStore.getState().scope !== key || authStore.getState().epoch !== authEpoch) return;
    const next: Session = { token: result.token, usuario: result.usuario, expiresAt: Date.now() + result.expiraEn * 1000 };
    queryClient.clear();
    if (!authStore.getState().setSession(key, next, authEpoch)) setNotice('La sesión no pudo guardarse; se perderá al recargar.');
  }
  function changeCloud(next: Cloud) {
    if (next === cloud) return;
    logout(); authStore.getState().switchScope(keyFor(next)); setCloud(next); setNotice('Cambiaste de nube. Inicia sesión en este ambiente.');
  }
  let configError = '';
  try { assertCloudReady(config, cloud); } catch (error) { configError = (error as Error).message; }
  const demo = config.mode === 'mock';
  const queryScope = `${key}:user:${session?.usuario.id || 'anonymous'}`;
  const provider = <div className="cloud-switch" aria-label="Ambiente cloud"><button className={cloud === 'aws' ? 'selected' : ''} aria-pressed={cloud === 'aws'} onClick={() => changeCloud('aws')}><span className="cloud-dot aws" />AWS</button><button className={cloud === 'azure' ? 'selected' : ''} aria-pressed={cloud === 'azure'} onClick={() => changeCloud('azure')}><span className="cloud-dot azure" />Azure</button></div>;
  const avatar = session?.usuario.urlImagenPerfil ? (demo ? mockAsset(localStorage, cloud, session.usuario.urlImagenPerfil) : session.usuario.urlImagenPerfil) : '';
  const safeAvatar = avatar.startsWith('https://') || /^data:image\/(png|jpeg|gif|webp);base64,/.test(avatar) ? avatar : '';
  return <>
    {session && !configError && <a className="skip-link" href="#main-content" onClick={() => {
      const main = document.getElementById('main-content');
      if (main) { main.tabIndex = -1; main.focus(); }
    }}>Saltar al contenido</a>}
    {!session || configError ? <><div className="auth-environment"><span className={`mode-label ${demo ? 'demo' : ''}`}>{demo ? 'DEMO LOCAL' : 'SERVICIOS REALES'}</span>{provider}</div>{configError ? <main className="config-error"><Icon name="cloud" size={42} /><h1>Este ambiente aún no está configurado.</h1><p role="alert">{configError}</p><p>Completa las URLs públicas en config.js, o selecciona el otro ambiente.</p></main> : <Auth key={`${cloud}:${config.mode}`} api={api} demo={demo} onLogin={login} />}</> : <div className="app-shell">
      <aside className="sidebar"><a className="brand" href="#tasks" onClick={() => setPage('tasks')}><span className="brand-mark"><Icon name="check" size={26} /></span>taskflow<span className="brand-dot">.</span></a><div className="workspace-name"><span>TF</span><div><strong>Mi espacio</strong><small>TaskFlow + CloudDrive</small></div></div><span className="nav-caption">TU DÍA, EN ORDEN</span><nav aria-label="Navegación principal"><button className={page === 'tasks' ? 'active' : ''} aria-current={page === 'tasks' ? 'page' : undefined} onClick={() => setPage('tasks')}><Icon name="tasks" />Mis tareas<Icon name="arrow" size={17} /></button><button className={page === 'drive' ? 'active' : ''} aria-current={page === 'drive' ? 'page' : undefined} onClick={() => setPage('drive')}><Icon name="cloud" />CloudDrive<Icon name="arrow" size={17} /></button></nav><div className="sidebar-note"><span className="note-spark">✦</span><strong>Un paso también<br />es progreso.</strong><p>No tienes que hacerlo todo hoy. Solo empieza por algo.</p></div><div className="sidebar-bottom"><span className={`mode-label ${demo ? 'demo' : ''}`}>{demo ? 'DEMO LOCAL' : 'SERVICIOS REALES'}</span><small>{demo ? 'Sin conexión a AWS o Azure' : `Conectado a ${cloud.toUpperCase()}`}</small><div className="user-row"><span className="avatar">{safeAvatar ? <img src={safeAvatar} alt="Tu imagen de perfil" /> : session.usuario.nombreUsuario.slice(0, 2).toUpperCase()}</span><div><strong>{session.usuario.nombreUsuario}</strong><small>Tu espacio personal</small></div><button className="icon-button" aria-label="Cerrar sesión" title="Cerrar sesión" onClick={logout}><Icon name="logout" size={19} /></button></div></div></aside>
      <div className="main-area"><header className="topbar"><div className="breadcrumb">Mi espacio <span>/</span><strong>{page === 'tasks' ? 'Mis tareas' : 'CloudDrive'}</strong></div><div className="topbar-right">{provider}<span className="header-avatar">{session.usuario.nombreUsuario.slice(0, 1).toUpperCase()}</span></div></header>{demo && <div className="demo-banner"><span className="demo-indicator" /><strong>Estás en modo demo.</strong><span>Los datos se guardan en este navegador, no en la nube.</span></div>}<main className="content" id="main-content" key={queryScope}>{page === 'tasks' ? <Tasks api={api} token={session.token} scope={queryScope} notify={setNotice} /> : <Drive api={api} token={session.token} userId={session.usuario.id} cloud={cloud} demo={demo} scope={queryScope} notify={setNotice} />}<footer className="workspace-footer"><span>MENOS RUIDO. MÁS CLARIDAD.</span><span>TaskFlow + CloudDrive · G15</span></footer></main></div>
    </div>}
    {notice && <div className="toast" role="status"><Icon name="check" size={18} /><span>{notice}</span><button className="icon-button" aria-label="Cerrar notificación" onClick={() => setNotice('')}><Icon name="close" size={16} /></button></div>}
  </>;
}
