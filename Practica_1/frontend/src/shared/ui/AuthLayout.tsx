import type { ReactNode } from 'react'
import AuthHeader from './AuthHeader'

interface AuthLayoutProps {
  children: ReactNode
  className?: string
}

function AuthLayout({ children, className = '' }: AuthLayoutProps) {
  return (
    <main className={`min-h-screen box-border bg-snow px-6 font-body text-ink ${className}`}>
      <AuthHeader />
      {children}
    </main>
  )
}

export default AuthLayout
