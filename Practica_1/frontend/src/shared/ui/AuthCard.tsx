import type { ReactNode } from 'react'

interface AuthCardProps {
  children: ReactNode
  labelledBy: string
  variant: 'login' | 'register'
}

const cardVariants = {
  login:
    'min-h-0 max-w-145 rounded-3xl px-14 pb-2 pt-4 max-auth:min-h-0 max-auth:px-6 max-auth:pb-5 max-auth:pt-5',
  register:
    'min-h-0 max-w-160 rounded-4xl px-15 pb-0 pt-3 max-auth:min-h-0 max-auth:rounded-3xl max-auth:px-6 max-auth:pb-5 max-auth:pt-5',
} as const

function AuthCard({ children, labelledBy, variant }: AuthCardProps) {
  return (
    <section
      className={`mx-auto box-border flex w-full flex-col items-center border border-mist bg-surface ${cardVariants[variant]}`}
      aria-labelledby={labelledBy}
    >
      {children}
    </section>
  )
}

export default AuthCard
