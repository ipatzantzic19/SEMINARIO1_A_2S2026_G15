import type { SVGProps } from 'react'

export type IconName =
  | 'arrow'
  | 'check'
  | 'compass'
  | 'heart'
  | 'menu'
  | 'play'
  | 'plus'
  | 'search'
  | 'user'

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName
  size?: number
}

function Icon({ name, size = 18, ...props }: IconProps) {
  const commonProps = {
    fill: 'none',
    stroke: 'currentColor',
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    strokeWidth: 1.8,
  }

  return (
    <svg
      aria-hidden="true"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      {...commonProps}
      {...props}
    >
      {name === 'arrow' && <path d="M5 12h13m-6-6 6 6-6 6" />}
      {name === 'check' && <path d="m5 12 4 4L19 6" />}
      {name === 'compass' && (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="m15.5 8.5-2.25 4.75L8.5 15.5l2.25-4.75z" />
        </>
      )}
      {name === 'heart' && <path d="M20.84 8.94a5.5 5.5 0 0 0-9-1.66 5.5 5.5 0 0 0-9 1.66c-1.54 3.44 1.37 6.68 9 11.06 7.63-4.38 10.54-7.62 9-11.06Z" />}
      {name === 'menu' && <path d="M4 7h16M4 12h16M4 17h16" />}
      {name === 'play' && <path d="m8 5 11 7-11 7z" />}
      {name === 'plus' && <path d="M12 5v14M5 12h14" />}
      {name === 'search' && (
        <>
          <circle cx="10.8" cy="10.8" r="6.8" />
          <path d="m16 16 4.5 4.5" />
        </>
      )}
      {name === 'user' && (
        <>
          <circle cx="12" cy="8" r="3.2" />
          <path d="M5.5 20a6.5 6.5 0 0 1 13 0" />
        </>
      )}
    </svg>
  )
}

export default Icon
