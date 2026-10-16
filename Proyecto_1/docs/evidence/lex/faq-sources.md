# Verificación de fuentes del bot (PRO-19)

Checklist para comprobar cada entrada de
[`infra/lex/faq.yaml`](../../../infra/lex/faq.yaml) contra el portal oficial
**antes** de cambiarla a `status: approved`.

El contenido se extrajo el 2026-10-15 con una herramienta externa y **ninguna
entrada está verificada**. Para cada fila: abrir la URL, buscar la frase con
Ctrl+F (en los PDF, con el buscador del visor), confirmar que el `excerpt` de
`faq.yaml` aparece literal y que la respuesta no dice más que el excerpt.
Anotar fecha y quién verificó.

| # | id | URL | Frase para buscar (Ctrl+F) | Estado | Verificó / fecha | Observaciones |
|---|---|---|---|---|---|---|
| 1 | `UbicacionContactoInstitucional` | https://portal.ingenieria.usac.edu.gt/ | `24189100` | pendiente | | Confirmar que 24189100 es un teléfono (la respuesta no lo etiqueta). |
| 2 | `HorarioControlAcademico` | https://academicoc.ingenieria.usac.edu.gt/index.php/2014-10-09-21-43-54 | `Horario de atención: 08:00-13:00` | verificada por Javier, 2026-10-15 | Javier, 2026-10-15 | Excerpt recortado para excluir un correo de Gmail; la ubicación (Edificio T-4) quedó fuera de la respuesta. |
| 3 | `OfertaAcademicaEscuelas` | https://portal.ingenieria.usac.edu.gt/index.php/destacados-2/1291-escuelas | `Industrias Agropecuarias y Forestales` | verificada por Javier, 2026-10-15 | Javier, 2026-10-15 | Página de noviembre de 2018: confirmar que el listado y los nombres sigan vigentes y que la lista esté completa. |
| 4 | `IngresoMaestriasAspirantes` | https://postgrado.ingenieria.usac.edu.gt/programas-de-maestria/ | `Del año a inscribirse` | pendiente | | Verificar también la frase "existen otras modalidades con requisitos distintos" (viene de una nota de la extracción, no del excerpt). |
| 5 | `FAQRequisitoMinimoPosgrado` (varios turnos) | https://postgrado.ingenieria.usac.edu.gt/preguntas-frecuentes/ | `requisito mínimo para optar a un postgrado` | pendiente | | |
| 6 | `CursosExtracurricularesSoporte` | https://extracurriculares.ingenieria.usac.edu.gt/inicio | `soportesaesap@ingenieria.usac.edu.gt` | verificada por Javier, 2026-10-15 | Javier, 2026-10-15 | |
| 7 | `CierreDePensumMaestria` | https://postgrado.ingenieria.usac.edu.gt/noticias/cierre-de-pensum-de-programas-de-maestria/ | `24 a 72 horas` | pendiente | | Noticia sin fecha: confirmar vigencia del procedimiento. |
| 8 | `RequisitosPruebasEspecificasVirtuales` | https://primeringreso.ingenieria.usac.edu.gt/iniciodeespecificas | `Acta No. 25-21` | pendiente | | Resolución aplicable desde las pruebas para ingresar a 2022: confirmar vigencia. |
| 9 | `OficinasVirtualesAtencion` | https://portal.ingenieria.usac.edu.gt/ | `oficinas virtuales vía ZOOM` | pendiente | | Revisar además https://portal.ingenieria.usac.edu.gt/oficinas-virtuales (fuente adicional sin verificar, no usada en la respuesta). |
| 10 | `EPSRequisitosAsignacion` | https://portal.ingenieria.usac.edu.gt/reglamentos/NormativoEPS.pdf | `Solvencia de EPS Inicial` | pendiente | | PDF; el excerpt empieza en el inciso d). |
| 11 | `EquivalenciasEvaluacionSuficiencia` | https://portal.ingenieria.usac.edu.gt/reglamentos/NormativoGeneral_Evaluacion_y_Promocion.pdf | `Artículo 55º` | pendiente | | PDF; solo artículos 54 y 55. |
| 12 | `fallback` | — | — | pendiente | | Revisar la redacción y que la lista de temas coincida con las entradas aprobadas. |

## Temas sin información en la base de conocimiento

La extracción no obtuvo contenido para estos temas; el fallback remite al
portal oficial en lugar de responderlos:

- Calendario académico del semestre vigente.
- Proceso de revisión de trabajo de graduación.
- Preguntas frecuentes de pregrado.
