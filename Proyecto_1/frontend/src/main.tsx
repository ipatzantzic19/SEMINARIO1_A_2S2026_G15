import React, { useEffect, useState } from 'react';
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import { clearSession, readSession, saveSession } from './session';
import { readConfig } from './config';
import { loadPreview, type PreviewState } from './mock';
import './styles.css';

const config = readConfig();

function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const isLogin = mode === 'login';
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!config.useMocks) { setError('El formulario real se implementa en PRO-21. La navegación base ya está lista.'); return; }
    saveSession({ accessToken: 'mock-token-local', profileComplete: true });
    navigate('/feed', { replace: true });
  }
  return <main className="auth-layout"><section className="auth-card"><span className="eyebrow">SEMI-SOCIAL · G15</span><h1>{isLogin ? 'Qué bueno verte.' : 'Únete a la conversación.'}</h1><p className="muted">{isLogin ? 'Ingresa para explorar tu comunidad.' : 'Esta pantalla base se conectará con Cognito en PRO-21.'}</p><form onSubmit={submit}><label>Correo electrónico<input type="email" placeholder="tu@correo.com" required /></label><label>Contraseña<input type="password" minLength={8} placeholder="••••••••" required /></label>{error && <p role="alert" className="error">{error}</p>}<button type="submit">{isLogin ? 'Entrar' : 'Crear cuenta'}</button></form><p className="switch">{isLogin ? '¿Aún no tienes cuenta?' : '¿Ya tienes cuenta?'} <Link to={isLogin ? '/registro' : '/login'}>{isLogin ? 'Regístrate' : 'Inicia sesión'}</Link></p>{config.useMocks && <p className="mock-note">Modo demostración: no se envían credenciales ni se crea una cuenta real.</p>}</section></main>;
}

function ProtectedLayout() {
  const navigate = useNavigate();
  const [session, setSession] = useState(readSession);
  useEffect(() => { const sync = () => setSession(readSession()); window.addEventListener('semisocial:session', sync); return () => window.removeEventListener('semisocial:session', sync); }, []);
  if (!session) return <Navigate to="/login" replace />;
  function logout() { clearSession(); setSession(null); navigate('/login', { replace: true }); }
  return <div className="app-shell"><header><Link className="brand" to="/feed">semi<span>social</span></Link><nav aria-label="Principal"><Link to="/feed">Inicio</Link><Link to="/usuarios">Personas</Link><Link to="/chat">Chat</Link><Link to="/perfil">Mi perfil</Link></nav><button className="secondary" onClick={logout}>Salir</button></header><Outlet /></div>;
}

const basePages: Record<string, { title: string; description: string; next: string }> = {
  feed: { title: 'Tu comunidad, en un lugar.', description: 'Aquí aparecerán las publicaciones tuyas y de tus amigos.', next: 'PRO-36 · publicaciones y feed' },
  usuarios: { title: 'Conoce a tu gente.', description: 'Busca personas y gestiona tus solicitudes de amistad.', next: 'PRO-22 · usuarios y amistades' },
  chat: { title: 'La conversación sigue.', description: 'Tus conversaciones con amigos vivirán aquí.', next: 'PRO-23 · chat en tiempo real' },
  perfil: { title: 'Tu espacio personal.', description: 'Tu información y foto de perfil se mostrarán aquí.', next: 'PRO-21 · identidad y perfil' }
};

function BasePage({ page }: { page: keyof typeof basePages }) {
  const data = basePages[page];
  const [preview, setPreview] = useState<{ state: PreviewState; label?: string }>({ state: 'loading' });
  useEffect(() => { let active = true; setPreview({ state: 'loading' }); loadPreview(page).then(result => { if (active) setPreview(result); }).catch(() => { if (active) setPreview({ state: 'error' }); }); return () => { active = false; }; }, [page]);
  return <main className="content"><span className="eyebrow">SEMI-SOCIAL</span><h1>{data.title}</h1><p className="muted">{data.description}</p><div className="empty-state" aria-live="polite"><span aria-hidden="true">✦</span><h2>{preview.state === 'loading' ? 'Cargando…' : preview.state === 'error' ? 'No pudimos cargar esta sección' : preview.state === 'empty' ? 'Aún no hay contenido' : 'Vista de ejemplo'}</h2><p>{preview.state === 'error' ? 'Vuelve a intentarlo más tarde.' : preview.label ?? 'La navegación y sesión ya funcionan. Esta sección se completará en su ticket de implementación.'}</p><small>{data.next}</small></div></main>;
}

export function App() {
  return <BrowserRouter><Routes><Route path="/login" element={<AuthPage mode="login" />} /><Route path="/registro" element={<AuthPage mode="register" />} /><Route element={<ProtectedLayout />}><Route path="/feed" element={<BasePage page="feed" />} /><Route path="/usuarios" element={<BasePage page="usuarios" />} /><Route path="/chat" element={<BasePage page="chat" />} /><Route path="/perfil" element={<BasePage page="perfil" />} /></Route><Route path="*" element={<Navigate to={readSession() ? '/feed' : '/login'} replace />} /></Routes></BrowserRouter>;
}
