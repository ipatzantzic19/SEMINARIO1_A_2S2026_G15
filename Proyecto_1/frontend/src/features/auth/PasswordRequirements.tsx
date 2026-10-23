import { Check, Minus } from "lucide-react";

type PasswordRequirementsProps = {
  password: string;
  repeatedPassword: string;
};

const SPECIAL_CHARACTER = /[\^$*.[\]{}()?"!@#%&/\\,><':;|_~`=+-]/;

export function PasswordRequirements({
  password,
  repeatedPassword,
}: PasswordRequirementsProps) {
  const requirements = [
    { label: "12 caracteres como mínimo", met: password.length >= 12 },
    { label: "Una letra mayúscula", met: /[A-Z]/.test(password) },
    { label: "Una letra minúscula", met: /[a-z]/.test(password) },
    { label: "Un número", met: /\d/.test(password) },
    { label: "Un símbolo especial", met: SPECIAL_CHARACTER.test(password) },
    {
      label: "Ambas contraseñas coinciden",
      met: repeatedPassword.length > 0 && password === repeatedPassword,
    },
  ];

  return (
    <section
      className="password-requirements"
      aria-label="Requisitos de la contraseña"
      aria-live="polite"
    >
      <p>Tu contraseña debe incluir:</p>
      <ul>
        {requirements.map(({ label, met }) => (
          <li
            key={label}
            className={met ? "password-requirement--met" : undefined}
          >
            {met ? <Check aria-hidden="true" /> : <Minus aria-hidden="true" />}
            <span>{label}</span>
            <span className="visually-hidden">
              {met ? "Cumplido" : "Pendiente"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
