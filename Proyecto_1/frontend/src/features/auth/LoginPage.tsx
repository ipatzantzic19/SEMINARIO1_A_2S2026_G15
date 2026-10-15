import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Camera } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { endpoints } from '../../lib/api/endpoints'
import { errorMessage, isConfigured } from '../../lib/api/client'
import type { TokenSet } from '../../lib/api/types'
import { Button, Field, Notice } from '../../shared/ui'
import { AuthLayout } from './AuthLayout'
import { loginSchema, type LoginData } from './schemas'
import { useSession } from './session'

export function LoginPage() {
  const navigate = useNavigate()
  const setTokens = useSession((state) => state.setTokens)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const demo = import.meta.env.DEV && import.meta.env.MODE === 'demo'
  const { register, handleSubmit, formState: { errors } } = useForm<LoginData>({ resolver: zodResolver(loginSchema) })

  async function submit(raw: LoginData) {
    setBusy(true); setError('')
    try {
      const response = await endpoints.login(loginSchema.parse(raw))
      if (response.status === 202) { setError('Tu cuenta requiere un desafío adicional de Cognito. El equipo backend debe definir este paso antes de iniciar sesión.'); return }
      const tokens = response.data as TokenSet
      setTokens(tokens)
      navigate(tokens.profileComplete ? '/' : '/complete-profile')
    } catch (failure) { setError(errorMessage(failure)) } finally { setBusy(false) }
  }

  return <AuthLayout>
    <h2>Entra a tu comunidad</h2><p className="muted">Continúa con tu cuenta o usa el acceso facial.</p>
    {demo ? <Notice>Modo de prueba local: crea una cuenta y confirma con cualquier código numérico de 6 a 8 dígitos. Los datos simulados solo viven en memoria; no se crea una cuenta AWS.</Notice> : !isConfigured() && <Notice>Entorno de integración pendiente: configura las dos URL de API en <code>.env</code> antes de iniciar sesión.</Notice>}
    {error && <Notice kind="error">{error}</Notice>}
    <form onSubmit={handleSubmit(submit)} noValidate>
      <Field id="email" label="Correo electrónico" type="email" autoComplete="email" placeholder="nombre@correo.com" error={errors.email?.message} {...register('email')} />
      <Field id="password" label="Contraseña" type="password" autoComplete="current-password" error={errors.password?.message} {...register('password')} />
      <Button type="submit" loading={busy} className="full">Entrar con contraseña</Button>
    </form>
    <div className="auth-separator">o bien</div>
    <Link className="button button--secondary full" to="/login/face"><Camera size={18} />Entrar con reconocimiento facial</Link>
    <p className="auth-next">¿Aún no tienes cuenta? <Link to="/register">Crear cuenta</Link></p>
  </AuthLayout>
}
