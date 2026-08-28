import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../../../stores/auth.store'
import { obtenerApiError } from '../../../lib/api/errors'
import AppShell from '../../../shared/ui/AppShell'
import AuthErrorAlert from '../../../shared/ui/AuthErrorAlert'
import Icon from '../../../shared/ui/Icon'
import ProfilePhotoPicker from '../../../shared/ui/ProfilePhotoPicker'
import PrimaryButton from '../../../shared/ui/PrimaryButton'
import TextField from '../../../shared/ui/TextField'
import { actualizarPerfil, consultarPerfil } from '../api'
import { profileSchema, type ProfileFormValues } from '../schema'
import type { Usuario } from '../../auth/types'

const valoresIniciales: ProfileFormValues = {
  nombreCompleto: '',
  contrasenaActual: '',
  fotoPerfil: null,
}

function esErrorDeAutenticacion(codigo: string) {
  return ['ERROR_AUTENTICACION', 'NO_AUTORIZADO', 'TOKEN_INVALIDO'].includes(codigo)
}

function esContrasenaActualInvalida(codigo: string, mensaje: string) {
  return codigo === 'CONTRASENA_ACTUAL_INVALIDA' || /contraseña actual/i.test(mensaje)
}

function ProfilePage() {
  const navigate = useNavigate()
  const usuarioInicial = useAuthStore((state) => state.usuario)
  const updateUsuario = useAuthStore((state) => state.updateUsuario)
  const clearSession = useAuthStore((state) => state.clearSession)
  const [perfil, setPerfil] = useState<Usuario | null>(usuarioInicial)
  const [isLoading, setIsLoading] = useState(true)
  const [profileError, setProfileError] = useState('')
  const [formError, setFormError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const {
    control,
    handleSubmit,
    register,
    reset,
    setError,
    setValue,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    mode: 'onBlur',
    defaultValues: valoresIniciales,
  })

  const selectedPhoto = useWatch({ control, name: 'fotoPerfil' })

  useEffect(() => {
    const controller = new AbortController()

    consultarPerfil(controller.signal)
      .then((usuario) => {
        setPerfil(usuario)
        updateUsuario(usuario)
        reset({
          nombreCompleto: usuario.nombreCompleto,
          contrasenaActual: '',
          fotoPerfil: null,
        })
        setProfileError('')
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return

        const apiError = obtenerApiError(requestError)
        if (esErrorDeAutenticacion(apiError.codigo)) {
          clearSession()
          navigate('/login', { replace: true })
          return
        }
        setProfileError(apiError.mensaje)
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false)
      })

    return () => controller.abort()
  }, [clearSession, navigate, reset, updateUsuario])

  const onSubmit = async (values: ProfileFormValues) => {
    setFormError('')
    setSuccessMessage('')

    if (!perfil) return

    const nombreCompleto = values.nombreCompleto.trim()
    const cambioDeNombre = nombreCompleto !== perfil.nombreCompleto.trim()
    const cambioDeFoto = Boolean(values.fotoPerfil)

    if (!cambioDeNombre && !cambioDeFoto) {
      setFormError('Modifica tu nombre o selecciona una fotografía antes de guardar.')
      return
    }

    try {
      const usuarioActualizado = await actualizarPerfil({
        contrasenaActual: values.contrasenaActual,
        ...(cambioDeNombre ? { nombreCompleto } : {}),
        fotoPerfil: values.fotoPerfil,
      })

      setPerfil(usuarioActualizado)
      updateUsuario(usuarioActualizado)
      reset({
        nombreCompleto: usuarioActualizado.nombreCompleto,
        contrasenaActual: '',
        fotoPerfil: null,
      })
      setSuccessMessage('Cambios guardados correctamente.')
    } catch (requestError: unknown) {
      const apiError = obtenerApiError(requestError)
      const passwordError = esContrasenaActualInvalida(apiError.codigo, apiError.mensaje)

      apiError.detalles.forEach((detail) => {
        const camposPermitidos: Array<keyof ProfileFormValues> = [
          'nombreCompleto',
          'contrasenaActual',
          'fotoPerfil',
        ]

        if (detail.campo && camposPermitidos.includes(detail.campo as keyof ProfileFormValues)) {
          setError(detail.campo as keyof ProfileFormValues, { message: detail.mensaje })
        }
      })

      if (passwordError) {
        setError('contrasenaActual', { message: apiError.mensaje })
        return
      }

      if (esErrorDeAutenticacion(apiError.codigo)) {
        clearSession()
        navigate('/login', { replace: true })
        return
      }

      setFormError(apiError.mensaje)
    }
  }

  const cancelarEdicion = () => {
    if (!perfil) return

    reset({
      nombreCompleto: perfil.nombreCompleto,
      contrasenaActual: '',
      fotoPerfil: null,
    })
    setFormError('')
    setSuccessMessage('')
  }

  const inicial = perfil?.nombreCompleto.trim().slice(0, 1).toUpperCase() || 'C'

  return (
    <AppShell>
      <main className="mx-auto max-w-7xl px-5 py-9 sm:px-8 sm:py-12 lg:px-17 lg:py-20">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_31.5rem] lg:gap-16">
          <section className="flex min-h-[calc(100vh-11rem)] flex-col">
            <header className="max-w-140">
              <p className="m-0 font-body text-xs font-bold uppercase tracking-[2.6px] text-slate">Cuenta</p>
              <h1 className="mt-6 m-0 font-display text-5xl font-bold leading-[0.95] tracking-[-2px] text-ink sm:text-6xl">Mi perfil</h1>
              <p className="mt-6 m-0 max-w-130 font-body text-base leading-[1.45] text-slate sm:text-lg">
                Mantén tus datos al día. Para proteger tu cuenta, confirma tu contraseña actual antes de guardar.
              </p>
            </header>

            <div className="mt-14">
              <ProfilePhotoPicker
                details={(
                  <>
                    <p className="m-0 font-display text-2xl font-bold leading-none tracking-[-0.7px] text-ink">{perfil?.nombreCompleto || 'Cargando perfil'}</p>
                    <p className="mt-3 m-0 font-body text-sm text-slate">{perfil?.correoElectronico || ' '}</p>
                  </>
                )}
                fallbackText={inicial}
                id="profile-photo"
                initialPreviewUrl={perfil?.urlFotoPerfil}
                key={perfil?.urlFotoPerfil || 'profile-photo'}
                label="Cambiar fotografía"
                onFileChange={(file) => setValue('fotoPerfil', file, { shouldDirty: true, shouldValidate: true })}
                value={selectedPhoto ?? null}
                variant="compact"
              />
              <div className="sr-only" aria-live="polite">
                {selectedPhoto ? `Nueva fotografía seleccionada: ${selectedPhoto.name}` : ''}
              </div>
            </div>

            <p className="mt-auto max-w-130 pt-16 font-body text-sm leading-[1.45] text-slate">
              Tus cambios se reflejarán en todas tus sesiones después de guardarlos correctamente.
            </p>
          </section>

          <section className="rounded-3xl border border-mist bg-surface px-7 py-8 sm:px-10 sm:py-10" aria-labelledby="edit-profile-title">
            <h2 id="edit-profile-title" className="m-0 font-display text-2xl font-bold leading-none tracking-[-0.8px] text-ink">Editar información</h2>
            <p className="mt-5 m-0 font-body text-sm leading-[1.4] text-slate">Solo puedes modificar tu nombre y tu fotografía de perfil.</p>

            {profileError && (
              <div className="mt-8 rounded-2xl border border-red-300 bg-red-50 px-4 py-3 font-body text-sm leading-[1.35] text-red-900" role="alert">
                <p className="m-0">{profileError}</p>
                <button className="mt-3 font-body text-sm font-bold underline underline-offset-4" onClick={() => window.location.reload()} type="button">Intentar de nuevo</button>
              </div>
            )}
            {formError && <div className="mt-8"><AuthErrorAlert>{formError}</AuthErrorAlert></div>}
            {successMessage && (
              <div className="mt-8 flex items-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 font-body text-sm text-emerald-900" role="status">
                <Icon name="check" size={16} />
                <span>{successMessage}</span>
              </div>
            )}

            <form className="mt-12 flex flex-col gap-8" onSubmit={handleSubmit(onSubmit)} noValidate>
              <TextField
                id="profile-name"
                type="text"
                autoComplete="name"
                label="Nombre completo"
                placeholder="Tu nombre y apellido"
                inputClassName="h-15 rounded-2xl border-2 bg-snow px-5 text-base"
                labelClassName="text-sm"
                error={errors.nombreCompleto?.message}
                disabled={isLoading || !perfil}
                {...register('nombreCompleto')}
              />

              <div>
                <TextField
                  id="current-password"
                  type="password"
                  autoComplete="current-password"
                  label="Contraseña actual · requerida"
                  placeholder="Ingresa tu contraseña actual"
                  inputClassName="h-15 rounded-2xl border-2 bg-snow px-5 text-base"
                  labelClassName="text-sm"
                  error={errors.contrasenaActual?.message}
                  disabled={isLoading || !perfil}
                  {...register('contrasenaActual')}
                />
                <p className="mt-3 m-0 font-body text-xs leading-[1.35] text-slate">La contraseña se valida antes de aceptar cualquier cambio.</p>
              </div>

              <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center">
                <PrimaryButton className="h-14 px-5 text-sm sm:w-auto sm:min-w-50" type="submit" disabled={isLoading || !perfil || isSubmitting || !isDirty}>
                  {isSubmitting ? 'Guardando…' : 'Guardar cambios'}
                </PrimaryButton>
                <button
                  className="h-14 cursor-pointer rounded-2xl border-0 bg-transparent px-5 font-body text-sm font-bold text-slate transition hover:text-ink focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-4 disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                  onClick={cancelarEdicion}
                  disabled={isLoading || !perfil || isSubmitting || !isDirty}
                >
                  Cancelar
                </button>
              </div>
            </form>
          </section>
        </div>
      </main>
    </AppShell>
  )
}

export default ProfilePage
