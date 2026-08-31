import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../../stores/auth.store'
import Icon, { type IconName } from './Icon'

type AppPath = '/galeria' | '/mi-lista' | '/perfil'

interface AppShellProps {
  children: ReactNode
}

const navigationItems: Array<{ label: string; path: AppPath; icon: IconName }> = [
  { label: 'Explorar', path: '/galeria', icon: 'compass' },
  { label: 'Mi lista', path: '/mi-lista', icon: 'heart' },
  { label: 'Mi perfil', path: '/perfil', icon: 'user' },
]

function NavigationLink({
  item,
  compact = false,
}: {
  item: (typeof navigationItems)[number]
  compact?: boolean
}) {
  return (
    <NavLink
      className={({ isActive }) =>
        `group flex items-center gap-3 no-underline transition-colors focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2 ${
          compact
            ? `rounded-xl px-3 py-2 text-xs ${isActive ? 'bg-ink text-snow' : 'text-slate hover:bg-snow hover:text-ink'}`
            : `rounded-xl px-3 py-2.5 text-sm ${isActive ? 'bg-snow font-bold text-ink' : 'text-slate hover:bg-snow/75 hover:text-ink'}`
        }`
      }
      to={item.path}
    >
      <Icon name={item.icon} size={compact ? 15 : 17} />
      <span>{item.label}</span>
    </NavLink>
  )
}

function AppShell({ children }: AppShellProps) {
  const navigate = useNavigate()
  const usuario = useAuthStore((state) => state.usuario)
  const clearSession = useAuthStore((state) => state.clearSession)
  const inicial = usuario?.nombreCompleto.trim().slice(0, 1).toUpperCase() || 'C'

  const handleLogout = () => {
    clearSession()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-snow text-ink lg:flex">
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col bg-surface px-6 py-8 lg:flex">
        <NavLink className="no-underline focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-4" to="/galeria">
          <span className="block font-display text-[22px] font-bold leading-none tracking-[-0.8px] text-ink">CLOUDCINEMA</span>
          <span className="mt-2 block font-body text-[10px] font-medium uppercase tracking-[2.3px] text-slate">Tu biblioteca</span>
        </NavLink>

        <nav aria-label="Navegación principal" className="mt-18 flex flex-col gap-2">
          {navigationItems.map((item) => <NavigationLink item={item} key={item.path} />)}
        </nav>

        <div className="mt-auto">
          <button
            aria-label="Cerrar sesión"
            className="flex w-full cursor-pointer items-center gap-3 rounded-xl border-0 bg-transparent px-3 py-2.5 text-left font-body text-sm text-slate transition-colors hover:bg-snow hover:text-ink focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2"
            onClick={handleLogout}
            type="button"
          >
            <Icon name="logout" size={17} />
            <span>Cerrar sesión</span>
          </button>
          <p className="mt-5 m-0 font-body text-xs text-slate">G15 · Seminario 1</p>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="border-b border-mist bg-surface px-5 py-4 lg:hidden">
          <div className="flex items-center justify-between gap-4">
            <NavLink className="no-underline" to="/galeria">
              <span className="block font-display text-lg font-bold leading-none tracking-[-0.6px] text-ink">CLOUDCINEMA</span>
              <span className="mt-1 block font-body text-[9px] uppercase tracking-[1.8px] text-slate">Tu biblioteca</span>
            </NavLink>
            <div className="flex items-center gap-2">
              <button
                aria-label="Cerrar sesión"
                className="grid h-9 w-9 cursor-pointer place-items-center rounded-full border border-mist bg-transparent text-slate transition-colors hover:border-ink hover:bg-snow hover:text-ink focus-visible:outline-2 focus-visible:outline-ink focus-visible:outline-offset-2"
                onClick={handleLogout}
                type="button"
              >
                <Icon name="logout" size={16} />
              </button>
              <NavLink
                aria-label="Abrir mi perfil"
                className="grid h-9 w-9 place-items-center rounded-full bg-mist font-display text-sm font-bold text-ink no-underline"
                to="/perfil"
              >
                {inicial}
              </NavLink>
            </div>
          </div>
          <nav aria-label="Navegación principal" className="mt-4 flex gap-2 overflow-x-auto">
            {navigationItems.map((item) => <NavigationLink compact item={item} key={item.path} />)}
          </nav>
        </header>

        <div className="min-h-screen">{children}</div>
      </div>
    </div>
  )
}

export default AppShell
