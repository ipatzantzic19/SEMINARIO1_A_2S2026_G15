import type { InputHTMLAttributes } from 'react'
import Icon from './Icon'

interface SearchFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
}

/**
 * Campo de búsqueda compartido para las vistas autenticadas.
 * Mantiene el estilo de los controles de shadcn: borde sutil, foco visible
 * y una superficie elevada para diferenciarlo del contenido.
 */
function SearchField({ label = 'Buscar', className = '', ...props }: SearchFieldProps) {
  return (
    <label className={`group relative flex w-full items-center ${className}`}>
      <span className="sr-only">{label}</span>
      <Icon
        className="pointer-events-none absolute left-3.5 text-slate transition-colors group-focus-within:text-ink"
        name="search"
        size={17}
      />
      <input
        {...props}
        aria-label={props['aria-label'] ?? label}
        className="h-11 w-full rounded-2xl border border-mist/80 bg-snow px-10 font-body text-sm text-ink shadow-sm outline-none transition-[border-color,box-shadow,background-color] placeholder:text-slate/90 hover:border-slate focus:border-ink focus:bg-white focus:shadow-focus-ring"
        type="search"
      />
    </label>
  )
}

export default SearchField
