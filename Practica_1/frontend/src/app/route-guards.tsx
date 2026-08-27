import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { selectIsAuthenticated, useAuthStore } from '../../stores/auth.store'

interface RouteGuardProps {
  children: ReactNode
}

export function PublicOnly({ children }: RouteGuardProps) {
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  return isAuthenticated ? <Navigate to="/galeria" replace /> : children
}

export function RequireAuth({ children }: RouteGuardProps) {
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  return isAuthenticated ? children : <Navigate to="/login" replace />
}

export function RootRedirect() {
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  return <Navigate to={isAuthenticated ? '/galeria' : '/login'} replace />
}
