interface PasswordMatchIndicatorProps {
  confirmation: string
  password: string
}

function PasswordMatchIndicator({ confirmation, password }: PasswordMatchIndicatorProps) {
  if (!confirmation) return null

  const matches = password === confirmation

  return (
    <p
      className={`m-0 flex shrink-0 items-center gap-1 font-body text-[9px] leading-none ${matches ? 'text-emerald-700' : 'text-red-800'}`}
      aria-live="polite"
    >
      <span aria-hidden="true">{matches ? '✓' : '!'}</span>
      {matches ? 'Coinciden' : 'No coinciden'}
    </p>
  )
}

export default PasswordMatchIndicator
