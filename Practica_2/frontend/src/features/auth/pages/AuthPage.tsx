import { useState } from 'react';
import type { FormEvent } from 'react';
import type { Api } from '../../../lib/api/index.ts';
import type { LoginResult } from '../types.ts';
import { prepareUpload } from '../../../shared/validation/uploads.ts';
import { validateForm } from '../../../shared/validation/schema.ts';
import { loginSchema, registrationSchema } from '../schemas.ts';
import { useAuthMutations } from '../hooks.ts';
import Icon from '../../../shared/ui/Icon.tsx';

export default function Auth({ api, demo, onLogin }: { api: Api; demo: boolean; onLogin: (result: LoginResult) => void }) {
  const [register, setRegister] = useState(false);
  const { signIn, signUp, uploadPhoto, busy } = useAuthMutations(api);
  const [error, setError] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [profileUrl, setProfileUrl] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    const nombreUsuario = String(form.get('username')).trim();
    const contrasena = String(form.get('password'));
    setError('');
    try {
      if (register) {
        const confirmation = String(form.get('confirmation'));
        const registration = validateForm(registrationSchema, { nombreUsuario, correoElectronico: String(form.get('email')).trim(), contrasena, confirmacionContrasena: confirmation });
        if (!photo) throw new Error('Selecciona una imagen de perfil.');
        let url = profileUrl;
        if (!url) {
          const prepared = await prepareUpload(photo, true);
          const result = await uploadPhoto.mutateAsync(prepared);
          url = result.archivo.urlObjeto;
          setProfileUrl(url); // Reutilizar la carga si el registro falla por usuario duplicado.
        }
        await signUp.mutateAsync({ ...registration, urlImagenPerfil: url });
        setRegister(false); // Si el login falla, reintentar login, no registrar la cuenta de nuevo.
      }
      onLogin(await signIn.mutateAsync(validateForm(loginSchema, { nombreUsuario, contrasena })));
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo iniciar sesión.'); }
  }
  async function demoLogin() {
    if (busy) return;
    setError('');
    try { onLogin(await signIn.mutateAsync({ nombreUsuario: 'demo', contrasena: 'Demo2026!' })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo abrir la demo.'); }
  }
  return <main className="auth-layout">
    <section className="auth-story">
      <a className="brand" href="#"><span className="brand-mark"><Icon name="check" size={26} /></span>taskflow<span className="brand-dot">.</span></a>
      <div className="story-body"><h1>Tareas y archivos, en un lugar.</h1><p>Organiza tus pendientes y accede a tus archivos.</p>
        <div className="story-card"><span className="story-check"><Icon name="check" /></span><div><strong>Tu próximo proyecto comienza aquí</strong><small>Tareas claras, archivos a mano.</small></div><span className="story-pill">Listo</span></div>
        <div className="story-note"><Icon name="cloud" size={24} /><span>TaskFlow + CloudDrive<br /><small>Un mismo espacio. Dos nubes.</small></span></div>
      </div><p className="story-footer">SEMINARIO 1 · GRUPO 15 <span>PRÁCTICA 02</span></p>
    </section>
    <section className="auth-form-wrap">
      <div className="auth-form"><h2>{register ? 'Crear cuenta' : 'Iniciar sesión'}</h2><p className="muted">{register ? 'Completa tus datos y elige una imagen de perfil.' : 'Introduce tus credenciales para acceder a tu espacio.'}</p>
        <div className="auth-tabs" role="group" aria-label="Acceso a tu cuenta"><button type="button" aria-pressed={!register} className={!register ? 'active' : ''} disabled={busy} onClick={() => { setRegister(false); setError(''); }}>Iniciar sesión</button><button type="button" aria-pressed={register} className={register ? 'active' : ''} disabled={busy} onClick={() => { setRegister(true); setError(''); }}>Crear cuenta</button></div>
        {error && <div className="error-box" role="alert">{error}</div>}
        <form onSubmit={submit}>
          <fieldset disabled={busy} className="form-fields">
            <label>Nombre de usuario<input name="username" placeholder="tu_usuario" autoComplete="username" required minLength={register ? 3 : undefined} maxLength={50} pattern={register ? '[a-z0-9_]{3,50}' : undefined} title="Entre 3 y 50 letras minúsculas, números o guion bajo." /></label>
            {register && <label>Correo electrónico<input name="email" type="email" placeholder="tu@correo.com" autoComplete="email" maxLength={254} required /></label>}
            <label>Contraseña<input name="password" type="password" placeholder={register ? 'Al menos 8 caracteres' : 'Tu contraseña'} autoComplete={register ? 'new-password' : 'current-password'} required minLength={register ? 8 : undefined} maxLength={72} /></label>
            {register && <><label>Confirmar contraseña<input name="confirmation" type="password" placeholder="Una vez más, por favor" autoComplete="new-password" required minLength={8} maxLength={72} /></label><label>Imagen de perfil<input name="photo" type="file" accept="image/jpeg,image/png,image/gif,image/webp" required={!photo} onChange={e => { setPhoto(e.target.files?.[0] || null); setProfileUrl(''); }} /><small>JPEG, PNG, GIF o WebP · máximo 3 MiB.</small></label></>}
            <button className="button primary auth-submit" type="submit">{busy ? 'Un momento…' : register ? 'Crear mi cuenta' : 'Entrar a mi espacio'}<Icon name="arrow" /></button>
          </fieldset>
        </form>
        {demo && <div className="demo-login"><p>¿Solo estás explorando?</p><button className="button outline" disabled={busy} onClick={demoLogin}>Probar con la cuenta demo <Icon name="arrow" size={17} /></button><small>Datos simulados en este navegador. No uses credenciales reales.</small></div>}
        <p className="auth-bottom"><Icon name="lock" size={14} /> {demo ? 'Modo demo · sin conexión a servicios cloud' : 'Tu sesión se guarda solo en esta pestaña'}</p>
      </div>
    </section>
  </main>;
}
