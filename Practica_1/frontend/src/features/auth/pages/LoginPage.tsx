import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { iniciarSesion } from '../api'
import { loginSchema, type LoginFormValues } from '../schemas'
import { obtenerApiError } from '../../../lib/api/errors'
import { useAuthStore } from '../../../../stores/auth.store'
import AuthCard from '../../../shared/ui/AuthCard'
import AuthErrorAlert from '../../../shared/ui/AuthErrorAlert'
import AuthLayout from '../../../shared/ui/AuthLayout'
import BrandMark from '../../../shared/ui/BrandMark'
import PrimaryButton from '../../../shared/ui/PrimaryButton'
import TextField from '../../../shared/ui/TextField'

interface LoginLocationState {
  registrationSuccess?: boolean
}

function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const setSession = useAuthStore((state) => state.setSession)
  const [formError, setFormError] = useState('')
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    mode: 'onBlur',
  })

  const registrationMessage = (location.state as LoginLocationState | null)?.registrationSuccess
    ? 'Tu cuenta fue creada. Ahora inicia sesión para continuar.'
    : ''

  const onSubmit = async (values: LoginFormValues) => {
    setFormError('')

    try {
      const response = await iniciarSesion({
        correoElectronico: values.correoElectronico.trim().toLowerCase(),
        contrasena: values.contrasena,
      })

      setSession(response.datos.token, response.datos.usuario, response.datos.expiraEn)
      navigate('/galeria', { replace: true })
    } catch (error) {
      const apiError = obtenerApiError(error)
      let hasFieldError = false

      apiError.detalles.forEach((detail) => {
        if (detail.campo === 'correoElectronico' || detail.campo === 'contrasena') {
          setError(detail.campo, { message: detail.mensaje })
          hasFieldError = true
        }
      })

      setFormError(hasFieldError ? '' : apiError.mensaje)
    }
  }

  return (
    <AuthLayout className="pb-5 max-auth:px-4 max-auth:pb-5">
      <AuthCard labelledBy="login-title" variant="login">
        <BrandMark size="register" />

        <p className="mt-2 mb-1.5 text-center font-body text-[11px] font-bold leading-none tracking-[2px] text-slate">
          TU ESPACIO PERSONAL
        </p>

        <h1
          id="login-title"
          className="m-0 flex flex-col text-center font-display text-[34px] font-bold leading-[1.06] tracking-[-1.5px] text-ink max-auth:text-[clamp(30px,9vw,36px)]"
        >
          <span>Inicia sesión en</span>
          <span>CloudCinema</span>
        </h1>

        <p className="mt-2.5 max-w-110 text-center font-body text-[15px] font-normal leading-[1.35] text-slate max-auth:text-sm">
          Accede a tu biblioteca, listas y reproducciones desde cualquier dispositivo.
        </p>

        {registrationMessage && (
          <p className="mt-4 w-full rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-center font-body text-sm leading-[1.35] text-emerald-900" role="status">
            {registrationMessage}
          </p>
        )}

        {formError && <AuthErrorAlert>{formError}</AuthErrorAlert>}

        <form className="mt-4 w-full" onSubmit={handleSubmit(onSubmit)} noValidate>
          <TextField
            id="email"
            type="email"
            placeholder="tu@correo.com"
            autoComplete="email"
            label="Correo electrónico"
            inputClassName="h-13 rounded-2xl px-5 text-base"
            labelClassName="mb-1.5 text-sm"
            error={errors.correoElectronico?.message}
            {...register('correoElectronico')}
          />
          <TextField
            id="login-password"
            type="password"
            placeholder="••••••••"
            autoComplete="current-password"
            label="Contraseña"
            inputClassName="mt-2 h-13 rounded-2xl px-5 text-base"
            labelClassName="mb-1.5 text-sm"
            error={errors.contrasena?.message}
            {...register('contrasena')}
          />
          <PrimaryButton className="mt-3 h-13 text-base" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Iniciando sesión…' : 'Continuar'}
          </PrimaryButton>
        </form>

        <div className="mt-3 text-center">
          <p className="m-0 font-body text-sm leading-[1.3] text-slate">¿Primera vez en CloudCinema?</p>
          <Link
            className="mt-2 inline-block font-body text-sm font-bold text-ink no-underline hover:underline hover:underline-offset-4 focus-visible:outline-[3px] focus-visible:outline-accent focus-visible:outline-offset-4"
            to="/registro"
          >
            Crear una cuenta
          </Link>
        </div>

        <p className="mt-4 max-w-105 text-center font-body text-[11px] leading-[1.35] text-slate">
          Al continuar, aceptas los Términos de uso y la Política de privacidad.
        </p>
      </AuthCard>
    </AuthLayout>
  )
}

export default LoginPage
