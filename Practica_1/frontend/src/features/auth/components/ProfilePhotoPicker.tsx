import SharedProfilePhotoPicker from '../../../shared/ui/ProfilePhotoPicker'

interface ProfilePhotoPickerProps {
  error?: string
  id: string
  label: string
  onFileChange: (file: File) => void
  value: File | null
}

/** Mantiene la API usada por registro y reutiliza el selector compartido. */
function ProfilePhotoPicker(props: ProfilePhotoPickerProps) {
  return <SharedProfilePhotoPicker {...props} />
}

export default ProfilePhotoPicker
