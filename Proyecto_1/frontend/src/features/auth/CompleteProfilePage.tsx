import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { endpoints } from '../../lib/api/endpoints'
import { errorMessage } from '../../lib/api/client'
import { Button, Notice } from '../../shared/ui'
import { PhotoField } from './PhotoField'
import { RegistrationLayout } from './RegistrationLayout'
import { useRegistration } from './registration'
import { useSession } from './session'

export function CompleteProfilePage() {
  const photo = useRegistration((state) => state.photo)
  const setPhoto = useRegistration((state) => state.setPhoto)
  const tokens = useSession((state) => state.tokens)
  const setTokens = useSession((state) => state.setTokens)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (tokens?.profileComplete) return <Navigate to="/" replace />

  async function complete() {
    if (!photo || !tokens) return
    setBusy(true); setError('')
    try {
      const { imageKey } = await endpoints.upload('profile', photo)
      await endpoints.completeProfile(imageKey)
      setTokens({ ...tokens, profileComplete: true })
      setPhoto(null)
    } catch (failure) { setError(errorMessage(failure)) }
    finally { setBusy(false) }
  }

  return <RegistrationLayout step={3} title="Dale rostro a tu perfil." intro="Solo tu foto pública se mostrará a otras personas. La referencia para acceso facial permanece privada.">
    <h2>Completa tu perfil</h2>
    <p className="muted">La foto es necesaria antes de usar las funciones sociales. Si recargaste la página, selecciónala de nuevo.</p>
    {error && <Notice kind="error">{error}</Notice>}
    <PhotoField photo={photo} onPhoto={setPhoto} onError={setError} title="Foto de perfil" />
    <Button type="button" onClick={complete} disabled={!photo} loading={busy}>Guardar foto y entrar</Button>
  </RegistrationLayout>
}
