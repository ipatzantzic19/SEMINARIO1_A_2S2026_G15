import { Link } from 'react-router-dom'

function AuthHeader() {
  return (
    <header className="mx-auto box-border flex h-23 max-w-324 items-start justify-between pt-8 max-auth:h-19 max-auth:pt-6.5">
      <Link
        className="font-display text-[26px] font-bold leading-none tracking-[-0.8px] text-ink no-underline focus-visible:outline-[3px] focus-visible:outline-accent focus-visible:outline-offset-4 max-auth:text-[22px]"
        to="/"
      >
        CLOUDCINEMA
      </Link>
      <button
        className="cursor-pointer border-0 bg-transparent p-0 font-body text-[18px] font-bold leading-none tracking-[3px] text-ink focus-visible:outline-[3px] focus-visible:outline-accent focus-visible:outline-offset-4"
        type="button"
        aria-label="Más opciones"
      >
        •••
      </button>
    </header>
  )
}

export default AuthHeader
