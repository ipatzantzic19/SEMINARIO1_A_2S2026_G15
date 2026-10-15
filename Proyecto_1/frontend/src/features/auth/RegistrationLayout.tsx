import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

const steps = ['Datos de cuenta', 'Confirmar correo', 'Foto de perfil']

export function RegistrationLayout({ step, title, intro, children }: { step: 1 | 2 | 3; title: string; intro: string; children: ReactNode }) {
  return <div className="registration-page">
    <header className="registration-header"><Link className="brand" to="/login">semi<span>social</span></Link><Link to="/login">Ya tengo cuenta</Link></header>
    <main className="registration-layout">
      <aside className="registration-lead"><h1>{title}</h1><p>{intro}</p><ol className="registration-steps">{steps.map((label, index) => <li className={step === index + 1 ? 'current' : step > index + 1 ? 'complete' : ''} key={label}><span>{index + 1}</span>{label}</li>)}</ol></aside>
      <section className="registration-panel panel">{children}</section>
    </main>
  </div>
}
