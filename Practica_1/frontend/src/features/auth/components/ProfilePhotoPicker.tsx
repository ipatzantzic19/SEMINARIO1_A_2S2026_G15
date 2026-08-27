import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { profilePhotoSchema } from '../schemas'

interface ProfilePhotoPickerProps {
  error?: string
  id: string
  label: string
  onFileChange: (file: File) => void
  value: File | null
}

function ProfilePhotoPicker({ error, id, label, onFileChange, value }: ProfilePhotoPickerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [cameraError, setCameraError] = useState('')
  const [selectionError, setSelectionError] = useState('')
  const [isCameraOpen, setIsCameraOpen] = useState(false)
  const [previewUrl, setPreviewUrl] = useState('')

  useEffect(() => {
    if (isCameraOpen && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [isCameraOpen])

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setIsCameraOpen(false)
  }

  const validateAndSelectFile = (file: File) => {
    const result = profilePhotoSchema.safeParse(file)

    if (!result.success) {
      setSelectionError(result.error.issues[0]?.message ?? 'La fotografía no es válida.')
      return
    }

    setSelectionError('')
    setCameraError('')
    setPreviewUrl((previousPreviewUrl) => {
      if (previousPreviewUrl) URL.revokeObjectURL(previousPreviewUrl)
      return URL.createObjectURL(file)
    })
    onFileChange(file)
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''

    if (file) validateAndSelectFile(file)
  }

  const openCamera = async () => {
    setCameraError('')

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError('Tu navegador no permite acceder a la cámara.')
      return
    }

    try {
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: 'user' },
      })
      setIsCameraOpen(true)
    } catch {
      setCameraError('No pudimos acceder a la cámara. Revisa los permisos del navegador.')
    }
  }

  const capturePhoto = () => {
    const video = videoRef.current

    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      setCameraError('La cámara todavía no está lista. Inténtalo de nuevo.')
      return
    }

    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')

    if (!context) {
      setCameraError('No pudimos procesar la fotografía.')
      return
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => {
      if (!blob) {
        setCameraError('No pudimos generar la fotografía.')
        return
      }

      const file = new File([blob], `cloudcinema-${Date.now()}.jpg`, { type: 'image/jpeg' })
      validateAndSelectFile(file)
      stopCamera()
    }, 'image/jpeg', 0.9)
  }

  const describedBy = `${id}-help${error || selectionError || cameraError ? ` ${id}-error` : ''}`
  const visibleError = error || selectionError || cameraError

  return (
    <div className="mt-2 w-full">
      <label className="mb-1.5 block font-body text-xs font-bold leading-[1.3] text-ink" htmlFor={`${id}-file`}>
        {label}
      </label>
      <div
        className={`flex min-h-20 w-full items-center justify-between gap-4 rounded-field border-2 border-dashed bg-snow px-4.5 py-2.5 max-auth:h-auto max-auth:min-h-20 max-auth:flex-col max-auth:items-start max-auth:gap-2 ${visibleError ? 'border-red-700' : 'border-mist'}`}
        aria-describedby={describedBy}
      >
        <div className="flex min-w-0 items-center gap-3">
          {previewUrl ? (
            <img className="h-14 w-14 shrink-0 rounded-xl object-cover" src={previewUrl} alt="Vista previa de la foto de perfil" />
          ) : (
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-xl border border-dashed border-mist font-body text-[9px] font-bold uppercase tracking-[0.8px] text-slate">
              Preview
            </div>
          )}
          <div className="min-w-0">
            <p className="m-0 truncate font-body text-xs font-normal leading-[1.25] text-slate">
              {value?.name || 'Selecciona una imagen desde tu dispositivo'}
            </p>
            <p id={`${id}-help`} className="mt-1 m-0 font-body text-[10px] leading-[1.25] text-slate">
              Formatos: JPG, PNG o WebP · Máx. 5 MB
            </p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3 max-auth:w-full max-auth:justify-between">
          <input
            ref={fileInputRef}
            className="sr-only"
            id={`${id}-file`}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
          />
          <button
            className="cursor-pointer border-0 bg-transparent p-0 font-body text-xs font-bold leading-none text-ink hover:underline hover:underline-offset-4"
            type="button"
            onClick={() => fileInputRef.current?.click()}
          >
            Subir archivo
          </button>
          <button
            className="cursor-pointer border-0 border-l border-solid border-mist bg-transparent py-0 pl-2 font-body text-xs font-bold leading-none text-ink hover:underline hover:underline-offset-4"
            type="button"
            onClick={openCamera}
          >
            Usar cámara
          </button>
        </div>
      </div>
      {visibleError && (
        <p id={`${id}-error`} className="mt-1 font-body text-xs leading-[1.3] text-red-800" role="alert">
          {visibleError}
        </p>
      )}

      {isCameraOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4" role="dialog" aria-modal="true" aria-labelledby="camera-dialog-title">
          <div className="w-full max-w-lg rounded-3xl bg-snow p-5 text-ink shadow-2xl">
            <div className="flex items-center justify-between gap-4">
              <h2 id="camera-dialog-title" className="font-display text-xl font-bold">Toma tu foto</h2>
              <button
                className="cursor-pointer border-0 bg-transparent p-1 font-body text-sm font-bold text-slate hover:text-ink"
                type="button"
                onClick={stopCamera}
              >
                Cerrar
              </button>
            </div>
            <video ref={videoRef} className="mt-4 aspect-video w-full rounded-2xl bg-ink object-cover" autoPlay playsInline />
            <div className="mt-4 flex gap-3">
              <button
                className="h-12 flex-1 cursor-pointer rounded-2xl border-0 bg-ink px-4 font-body text-sm font-bold text-snow hover:bg-ink-hover"
                type="button"
                onClick={capturePhoto}
              >
                Capturar foto
              </button>
              <button
                className="h-12 cursor-pointer rounded-2xl border border-mist bg-transparent px-4 font-body text-sm font-bold text-ink hover:bg-surface"
                type="button"
                onClick={stopCamera}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ProfilePhotoPicker
