/**
 * Formatea un Date u objeto fecha a string ISO 8601 UTC con milisegundos y sufijo Z.
 * Ejemplo: 2026-10-02T12:00:00.000Z
 */
export function formatearFechaISO(fecha: Date | string | null | undefined): string | null {
  if (!fecha) return null;
  const d = new Date(fecha);
  if (isNaN(d.getTime())) return null;
  return d.toISOString();
}
