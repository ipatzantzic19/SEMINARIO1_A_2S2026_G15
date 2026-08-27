interface BrandMarkProps {
  size?: 'login' | 'register'
}

const markSizes = {
  login: 'h-20 w-20 rounded-3xl',
  register: 'h-16 w-16 rounded-2xl',
} as const

function BrandMark({ size = 'login' }: BrandMarkProps) {
  return (
    <div
      className={`box-border flex flex-col items-center justify-center border-2 border-mist bg-snow ${markSizes[size]}`}
      aria-hidden="true"
    >
      <span className="font-display text-[28px] font-bold leading-[0.9] tracking-[-1px]">CC</span>
      <small className="mt-1.5 font-body text-[9px] font-bold leading-none tracking-[1.5px] text-slate">
        MEDIA
      </small>
    </div>
  )
}

export default BrandMark
