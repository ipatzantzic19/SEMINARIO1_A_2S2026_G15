interface AuthErrorAlertProps {
  children: string
}

function AuthErrorAlert({ children }: AuthErrorAlertProps) {
  return (
    <div
      className="mb-4 w-full rounded-2xl border border-red-300 bg-red-50 px-4 py-3 font-body text-sm leading-[1.35] text-red-900"
      role="alert"
    >
      {children}
    </div>
  )
}

export default AuthErrorAlert
