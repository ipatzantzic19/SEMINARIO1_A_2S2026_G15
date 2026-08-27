import { Link } from 'react-router-dom'
import AuthLayout from './AuthLayout'

interface ModulePlaceholderPageProps {
  eyebrow: string
  title: string
  description: string
}

const navigationItems = [
  { label: 'Iniciar sesión', to: '/login' },
  { label: 'Crear cuenta', to: '/registro' },
  { label: 'Galería', to: '/galeria' },
  { label: 'Mi lista', to: '/mi-lista' },
  { label: 'Perfil', to: '/perfil' },
]

function ModulePlaceholderPage({
  eyebrow,
  title,
  description,
}: ModulePlaceholderPageProps) {
  return (
    <AuthLayout className="pb-8 max-auth:px-4 max-auth:pb-6">
      <section className="mx-auto mt-10 w-full max-w-160 rounded-4xl border border-mist bg-surface px-10 py-12 max-auth:mt-6 max-auth:rounded-3xl max-auth:px-6 max-auth:py-9">
        <p className="m-0 font-body text-xs font-bold uppercase tracking-[2px] text-slate">
          {eyebrow}
        </p>
        <h1 className="mt-3 m-0 font-display text-5xl font-bold leading-[1.05] tracking-[-1.5px] text-ink max-auth:text-4xl">
          {title}
        </h1>
        <p className="mt-5 max-w-110 font-body text-base leading-[1.45] text-slate">
          {description}
        </p>
        <nav aria-label="Navegación principal" className="mt-8 flex flex-wrap gap-3">
          {navigationItems.map((item) => (
            <Link
              key={item.to}
              className="rounded-full border border-mist bg-snow px-4 py-2 font-body text-sm font-bold text-ink no-underline transition-colors hover:border-ink hover:bg-accent focus-visible:outline-[3px] focus-visible:outline-accent focus-visible:outline-offset-2"
              to={item.to}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </section>
    </AuthLayout>
  )
}

export default ModulePlaceholderPage
