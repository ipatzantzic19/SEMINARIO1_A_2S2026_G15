import { createBrowserRouter, Navigate } from 'react-router-dom'
import GalleryPage from '../pages/GalleryPage'
import PlaylistPage from '../pages/PlaylistPage'
import ProfilePage from '../pages/ProfilePage'
import ModulePlaceholderPage from '../shared/ui/ModulePlaceholderPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/login" replace />,
  },
  {
    path: '/login',
    element: (
      <ModulePlaceholderPage
        description="La pantalla de inicio de sesión se implementará en el ticket de autenticación."
        eyebrow="Acceso a CloudCinema"
        title="Iniciar sesión"
      />
    ),
  },
  {
    path: '/registro',
    element: (
      <ModulePlaceholderPage
        description="La pantalla de creación de cuenta se implementará en el ticket de autenticación."
        eyebrow="Únete a CloudCinema"
        title="Crear cuenta"
      />
    ),
  },
  {
    path: '/galeria',
    element: <GalleryPage />,
  },
  {
    path: '/perfil',
    element: <ProfilePage />,
  },
  {
    path: '/mi-lista',
    element: <PlaylistPage />,
  },
  {
    path: '*',
    element: <Navigate to="/login" replace />,
  },
])
