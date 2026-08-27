import type { ReactNode } from 'react'
import AuthHeader from './AuthHeader'

interface AuthLayoutProps {
  children: ReactNode
  className?: string
}

function AuthLayout({ children, className = '' }: AuthLayoutProps) {
  return (
    <main className={`flex min-h-screen flex-col box-border bg-snow px-6 font-body text-ink ${className}`}>
      <AuthHeader />
      <div className="flex flex-1 items-center justify-center max-auth:items-start">
        {children}
      </div>
    </main>
  )
}

export default AuthLayout
