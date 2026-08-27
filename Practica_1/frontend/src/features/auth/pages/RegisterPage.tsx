import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { registrarUsuario } from '../api'
import ProfilePhotoPicker from '../components/ProfilePhotoPicker'
import PasswordMatchIndicator from '../components/PasswordMatchIndicator'
import PasswordStrengthMeter from '../components/PasswordStrengthMeter'
import { registerSchema, type RegisterFormValues } from '../schemas'
import { obtenerApiError } from '../../../lib/api/errors'
import AuthCard from '../../../shared/ui/AuthCard'
import AuthErrorAlert from '../../../shared/ui/AuthErrorAlert'
import AuthLayout from '../../../shared/ui/AuthLayout'
import BrandMark from '../../../shared/ui/BrandMark'
import PrimaryButton from '../../../shared/ui/PrimaryButton'
import TextField from '../../../shared/ui/TextField'

function RegisterPage() {
  const navigate = useNavigate()
  const [formError, setFormError] = useState('')
  const {
    register,
    control,
    handleSubmit,
    setError,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    mode: 'onBlur',
    defaultValues: {
      correoElectronico: '',
      nombreCompleto: '',
      contrasena: '',
      confirmacionContrasena: '',
    },
  })

  const selectedPhoto = useWatch({ control, name: 'fotoPerfil' })
  const passwordValue = useWatch({ control, name: 'contrasena' })
  const confirmationValue = useWatch({ control, name: 'confirmacionContrasena' })

  const onSubmit = async (values: RegisterFormValues) => {
    setFormError('')

    try {
      await registrarUsuario({
        ...values,
        correoElectronico: values.correoElectronico.trim().toLowerCase(),
        nombreCompleto: values.nombreCompleto.trim(),
      })
      navigate('/login', { replace: true, state: { registrationSuccess: true } })
    } catch (error) {
      const apiError = obtenerApiError(error)
      let hasFieldError = false

      apiError.detalles.forEach((detail) => {
        const camposPermitidos: Array<keyof RegisterFormValues> = [
          'correoElectronico',
          'nombreCompleto',
          'contrasena',
          'confirmacionContrasena',
          'fotoPerfil',
        ]

        if (detail.campo && camposPermitidos.includes(detail.campo as keyof RegisterFormValues)) {
          setError(detail.campo as keyof RegisterFormValues, { message: detail.mensaje })
          hasFieldError = true
        }
      })

      setFormError(hasFieldError ? '' : apiError.mensaje)
    }
  }

  return (
    <AuthLayout className="pb-0 max-auth:px-4 max-auth:pb-6">
      <AuthCard labelledBy="register-title" variant="register">
        <BrandMark size="register" />

        <p className="mt-2 mb-1.5 text-center font-body text-[11px] font-bold leading-none tracking-[2px] text-slate">
          NUEVA CUENTA
        </p>

        <h1
          id="register-title"
          className="m-0 flex flex-col text-center font-display text-4xl font-bold leading-[1.06] tracking-[-1.5px] text-ink max-auth:text-[clamp(30px,9vw,36px)]"
        >
          <span>Crear tu cuenta</span>
        </h1>

        <p className="mt-1.5 max-w-110 text-center font-body text-sm font-normal leading-[1.35] text-slate">
          Completa tus datos para comenzar tu biblioteca personal.
        </p>

        {formError && <AuthErrorAlert>{formError}</AuthErrorAlert>}

        <form className="mt-3 flex w-full max-w-130 flex-col gap-1.5" onSubmit={handleSubmit(onSubmit)} noValidate>
          <TextField
            id="full-name"
            type="text"
            placeholder="Tu nombre y apellido"
            autoComplete="name"
            label="Nombre completo"
            inputClassName="h-11.5 rounded-field px-4.5 text-sm"
            labelClassName="mb-1.5 text-xs"
            error={errors.nombreCompleto?.message}
            {...register('nombreCompleto')}
          />

          <TextField
            id="register-email"
            type="email"
            placeholder="tu@correo.com"
            autoComplete="email"
            label="Correo electrónico"
            inputClassName="h-11.5 rounded-field px-4.5 text-sm"
            labelClassName="mb-1.5 text-xs"
            error={errors.correoElectronico?.message}
            {...register('correoElectronico')}
          />

          <div className="grid grid-cols-2 gap-3 max-auth:grid-cols-1 max-auth:gap-2.5">
            <TextField
              id="password"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              label="Contraseña"
              labelContainerClassName="mb-1.5"
              labelSuffix={<PasswordStrengthMeter value={passwordValue} />}
              inputClassName="h-11.5 rounded-field px-4.5 text-sm"
              labelClassName="text-xs"
              error={errors.contrasena?.message}
              {...register('contrasena')}
            />

            <TextField
              id="confirm-password"
              type="password"
              placeholder="••••••••"
              autoComplete="new-password"
              label="Confirmar contraseña"
              labelContainerClassName="mb-1.5"
              labelSuffix={<PasswordMatchIndicator password={passwordValue} confirmation={confirmationValue} />}
              inputClassName="h-11.5 rounded-field px-4.5 text-sm"
              labelClassName="text-xs"
              error={errors.confirmacionContrasena?.message}
              {...register('confirmacionContrasena')}
            />
          </div>

          <ProfilePhotoPicker
            id="profile-photo"
            label="Fotografía de perfil"
            value={selectedPhoto ?? null}
            onFileChange={(file) => setValue('fotoPerfil', file, { shouldDirty: true, shouldValidate: true })}
            error={errors.fotoPerfil?.message}
          />

          <PrimaryButton className="mt-0.5 h-12 text-base" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creando cuenta…' : 'Crear mi cuenta'}
          </PrimaryButton>
        </form>

        <div className="mt-4 flex items-center justify-center gap-2 text-center">
          <p className="m-0 font-body text-sm leading-[1.3] text-slate">¿Ya tienes una cuenta?</p>
          <Link
            className="font-body text-sm font-bold text-ink no-underline hover:underline hover:underline-offset-4 focus-visible:outline-[3px] focus-visible:outline-accent focus-visible:outline-offset-4"
            to="/login"
          >
            Iniciar sesión
          </Link>
        </div>
      </AuthCard>
    </AuthLayout>
  )
}

export default RegisterPage
