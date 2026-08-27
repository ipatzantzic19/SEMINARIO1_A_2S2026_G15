import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface PrimaryButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  className?: string
  showArrow?: boolean
}

function PrimaryButton({ children, className = '', showArrow = true, ...props }: PrimaryButtonProps) {
  return (
    <button
      className={`box-border w-full cursor-pointer rounded-2xl border-0 bg-ink font-body font-bold leading-none text-snow transition hover:-translate-y-px hover:bg-ink-hover focus-visible:outline-[3px] focus-visible:outline-accent focus-visible:outline-offset-4 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0 ${className}`}
      {...props}
    >
      {children}
      {showArrow && (
        <span className="ml-2 align-[-2px] text-xl font-normal leading-none" aria-hidden="true">
          →
        </span>
      )}
    </button>
  )
}

export default PrimaryButton
