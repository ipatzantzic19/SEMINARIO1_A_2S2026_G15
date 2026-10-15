# Evidencia de validación integral - PRO-26

Estado: **matriz preparada; ejecución integral bloqueada por dependencias de
Node/Python, frontend, ALB y servicios de integración**.

Fecha de actualización: 14 de octubre de 2026. Responsable de coordinación:
Isai Patzan. Este documento separa la evidencia existente de las pruebas que
todavía deben ejecutar los dueños de cada vertical. Una captura de configuración
no se considera una prueba funcional aprobada.

## Reglas de la validación

- Ejecutar siempre desde la URL pública/DNS del ALB, nunca desde una IP directa
  de EC2 ni desde servicios locales.
- Usar cuentas y objetos de prueba anonimizados; no registrar contraseñas,
  tokens, claves ni datos personales reales.
- Guardar fecha, URL, responsable, resultado, evidencia y fallo asociado.
- Repetir cada caso fallido después de la corrección y conservar el resultado
  anterior como historial.

## Matriz requisito -> ticket -> prueba -> evidencia

| Requisito | Ticket / responsable | Prueba funcional | Evidencia y estado |
| --- | --- | --- | --- |
| Arquitectura, contrato y modelo común | PRO-1 / Isai | Comparar contrato, rutas y modelo con el despliegue | `docs/api/contract.md`; base completada, falta validación E2E |
| IAM mínimo, VPC y SG | PRO-4 / Isai | Revisar acceso permitido/denegado y ausencia de permisos amplios | `docs/evidence/iam/report.md`, `network/report.md`; evidencia de configuración, prueba conjunta pendiente |
| RDS PostgreSQL y esquema | PRO-2 / Isai | Conectar desde backend autorizado, aplicar migraciones y ejecutar `database/tests/verify_schema.sql` | `docs/evidence/rds/report.md`; instancia disponible, migraciones/prueba pendientes |
| S3 de imágenes | PRO-3 / Isai | Subir/leer objeto con prefijo autorizado y rechazar escritura anónima | `docs/evidence/s3-images/report.md`; prueba funcional conjunta pendiente |
| Registro, confirmación y recuperación | PRO-5 + PRO-7/14 / Isai, Daniel, Javier | Registrar, confirmar código, iniciar sesión, recuperar y rechazar no confirmado | `docs/evidence/cognito/report.md`; pool real documentado, flujo API pendiente |
| Perfil completo y foto obligatoria | PRO-11, PRO-21 / Daniel, Guo | Completar foto con JWT, verificar `profileComplete` y bloquear feed incompleto | Pendiente de API Gateway/Lambda y frontend |
| Login facial y contrato de etiquetas | PRO-12, PRO-31 / Isai | Comparar rostro válido/no válido y claims; no emitir JWT propio | Pendiente; no se crea recurso de pago |
| Usuarios y amistades | PRO-8, PRO-15 / Daniel, Javier | Solicitar, aceptar, rechazar y consultar feed de amigos | Pendiente de ambos backends |
| Publicaciones, comentarios y filtros | PRO-9, PRO-10, PRO-16, PRO-17 / Daniel, Javier | Crear publicación con imagen, comentar y filtrar contenido | Pendiente de backends y frontend |
| Translate y Lex | PRO-18, PRO-19, PRO-42 / Javier, Daniel | Traducir a cuatro destinos y probar intención Lex | Pendiente de servicios y contratos finales |
| Chat en tiempo real | PRO-22, PRO-23 / equipo | Mensaje entre usuarios y persistencia/errores esperados | Pendiente |
| ALB con Node y Python | PRO-20, PRO-24 / Daniel, Javier, Guo | Ejecutar health checks, cambiar target y confirmar respuesta pública | Pendiente de URL/DNS final |
| Failover de EC2 | PRO-25 / equipo | Detener cada EC2 por separado, validar continuidad y recuperar sin cambiar código | Pendiente de coordinación y ventana de prueba |
| Seguridad transversal | PRO-26 / Isai | Revisar 401/403, CORS, secretos fuera del repositorio y ausencia de BD local | Parcial: revisión documental; pruebas públicas pendientes |

## Registro de ejecución

| Caso | Responsable | Estado | Fecha | Evidencia | Falla / repetición |
| --- | --- | --- | --- | --- | --- |
| RDS disponible y aislado de Internet | Isai | Preparado; migraciones pendientes | 2026-10-14 | `docs/evidence/rds/report.md` | Ejecutar desde backend autorizado |
| User Pool y cliente sin secreto | Isai | Preparado; integración API pendiente | 2026-10-14 | `docs/evidence/cognito/report.md` | Requiere PRO-7/14 |
| Flujos públicos completos | Equipo | Bloqueado | — | — | Requiere PRO-11/14/15/18/20/21/22/24/31/42 |
| Failover Node/Python | Equipo | Bloqueado | — | — | Requiere ALB y dos EC2 disponibles |

## Bloqueos y riesgos abiertos

1. La validación E2E depende de que los dueños publiquen sus APIs, frontend,
   ALB y contratos finales. PRO-26 no reemplaza sus pruebas de aceptación.
2. RDS usa temporalmente el subnet group default porque la consola no ofreció
   `semisocial-g15-db-subnets`; debe resolverse antes de reconciliar IaC.
3. No se marcará un requisito como aprobado solo por existir una captura de
   configuración. Se requiere resultado funcional reproducible.
4. Las pruebas que puedan generar cargos (Rekognition, Translate, Lex o
   almacenamiento adicional) deben ejecutarse solo con autorización explícita
   y límites del free tier confirmados.

## Handoff a PRO-27

La matriz queda lista para que cada integrante agregue su URL pública, fecha,
captura y resultado real. PRO-27 puede consolidar este reporte cuando se hayan
cerrado los bloqueos y repetido los casos fallidos; la edición final del manual
no forma parte de PRO-26.
