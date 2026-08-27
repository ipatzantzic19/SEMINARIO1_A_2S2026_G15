interface PasswordStrengthMeterProps {
  value: string
}

const MINIMUM_PASSWORD_LENGTH = 6

function PasswordStrengthMeter({ value }: PasswordStrengthMeterProps) {
  const progress = Math.min(value.length / MINIMUM_PASSWORD_LENGTH, 1)
  const isValid = value.length >= MINIMUM_PASSWORD_LENGTH
  const remainingCharacters = MINIMUM_PASSWORD_LENGTH - value.length

  return (
    <div className="flex shrink-0 items-center gap-1.5" aria-live="polite">
      <div
        className="h-1.5 w-14 overflow-hidden rounded-full bg-mist/45"
        role="progressbar"
        aria-label="Progreso de la contraseña"
        aria-valuemin={0}
        aria-valuemax={MINIMUM_PASSWORD_LENGTH}
        aria-valuenow={Math.min(value.length, MINIMUM_PASSWORD_LENGTH)}
      >
        <div
          className={`h-full rounded-full transition-[width,background-color] duration-200 ${isValid ? 'bg-emerald-600' : 'bg-slate'}`}
          style={{ width: `${progress * 100}%` }}
        />
      </div>
      <span className={`font-body text-[9px] leading-none ${isValid ? 'text-emerald-700' : 'text-slate'}`}>
        {isValid ? 'Listo' : value ? `Faltan ${remainingCharacters}` : 'Mín. 6'}
      </span>
    </div>
  )
}

export default PasswordStrengthMeter
