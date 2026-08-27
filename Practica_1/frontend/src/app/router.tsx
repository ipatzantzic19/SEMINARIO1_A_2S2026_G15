import { createBrowserRouter } from 'react-router-dom'
import { LoginPage, RegisterPage } from '../features/auth'
import GalleryPage from '../pages/GalleryPage'
import PlaylistPage from '../pages/PlaylistPage'
import ProfilePage from '../pages/ProfilePage'
import { PublicOnly, RequireAuth, RootRedirect } from './route-guards'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootRedirect />,
  },
  {
    path: '/login',
    element: (
      <PublicOnly>
        <LoginPage />
      </PublicOnly>
    ),
  },
  {
    path: '/registro',
    element: (
      <PublicOnly>
        <RegisterPage />
      </PublicOnly>
    ),
  },
  {
    path: '/galeria',
    element: (
      <RequireAuth>
        <GalleryPage />
      </RequireAuth>
    ),
  },
  {
    path: '/perfil',
    element: (
      <RequireAuth>
        <ProfilePage />
      </RequireAuth>
    ),
  },
  {
    path: '/mi-lista',
    element: (
      <RequireAuth>
        <PlaylistPage />
      </RequireAuth>
    ),
  },
  {
    path: '*',
    element: <RootRedirect />,
  },
])
