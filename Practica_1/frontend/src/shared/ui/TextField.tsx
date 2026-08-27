import type { InputHTMLAttributes, ReactNode } from 'react'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string
  inputClassName?: string
  label: string
  labelClassName?: string
  labelContainerClassName?: string
  labelSuffix?: ReactNode
}

function TextField({
  error,
  inputClassName = '',
  label,
  labelClassName = '',
  labelContainerClassName = '',
  labelSuffix,
  ...props
}: TextFieldProps) {
  const errorId = props.id ? `${props.id}-error` : undefined

  return (
    <div className="w-full">
      {labelSuffix ? (
        <div className={`flex items-center justify-between gap-2 ${labelContainerClassName}`}>
          <label className={`block font-body font-bold leading-[1.3] text-ink ${labelClassName}`} htmlFor={props.id}>
            {label}
          </label>
          {labelSuffix}
        </div>
      ) : (
        <label
          className={`mb-2 block font-body font-bold leading-[1.3] text-ink ${labelClassName}`}
          htmlFor={props.id}
        >
          {label}
        </label>
      )}
      <input
        aria-describedby={errorId}
        aria-invalid={Boolean(error)}
        className={`box-border w-full border-2 bg-snow font-body font-normal leading-none text-ink outline-none placeholder:text-slate focus:border-ink focus:shadow-focus-ring ${error ? 'border-red-700' : 'border-mist'} ${inputClassName}`}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-1.5 font-body text-xs leading-[1.3] text-red-800" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

export default TextField
