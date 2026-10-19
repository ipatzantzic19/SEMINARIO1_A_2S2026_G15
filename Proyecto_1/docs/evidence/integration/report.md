# Evidencia de validación integral - PRO-26

Estado: **matriz actualizada; ejecución integral parcialmente desbloqueada,
pero todavía bloqueada por el ALB/API de negocio, RDS y failover**.

Fecha de actualización: 18 de octubre de 2026. Responsable de coordinación:
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
| Backend Python y contrato OpenAPI | PRO-13/14 / Javier, Isai | Ejecutar la suite de contrato/configuración y verificar que el arranque falla cerrado sin variables críticas | `backend-python/tests/`; suite local **114 pruebas aprobadas**; integración pública pendiente |
| IAM mínimo, VPC y SG | PRO-4 / Isai | Revisar acceso permitido/denegado y ausencia de permisos amplios | `docs/evidence/iam/report.md`, `network/report.md`; evidencia de configuración, prueba conjunta pendiente |
| RDS PostgreSQL y esquema | PRO-2 / Isai | Conectar desde backend autorizado, aplicar migraciones y ejecutar `database/tests/verify_schema.sql` | `docs/evidence/rds/report.md`; red VPC, migraciones, seed y verificación aprobados; consulta Node/Python y subnet group pendientes |
| S3 de imágenes | PRO-3 / Isai | Subir/leer objeto con prefijo autorizado y rechazar escritura anónima | `docs/evidence/s3-images/report.md`; prueba funcional conjunta pendiente |
| Registro, confirmación y recuperación | PRO-5 + PRO-7/14 / Isai, Daniel, Javier | Registrar, confirmar código, iniciar sesión, recuperar y rechazar no confirmado | `docs/evidence/cognito/report.md`; pool real documentado, flujo API pendiente |
| Perfil completo y foto obligatoria | PRO-11, PRO-21 / Daniel, Guo | Completar foto con JWT, verificar `profileComplete` y bloquear feed incompleto | PRO-11 tiene endpoint de upload publicado y pruebas locales; integración con API de negocio/frontend pendiente |
| Login facial y contrato de etiquetas | PRO-12, PRO-31 / Isai | Comparar rostro válido/no válido y claims; no emitir JWT propio | Contrato y pruebas locales documentados; E2E pendiente; no se crea recurso de pago |
| Usuarios y amistades | PRO-8, PRO-15 / Daniel, Javier | Solicitar, aceptar, rechazar y consultar feed de amigos | Pendiente de ambos backends |
| Publicaciones, comentarios y filtros | PRO-9, PRO-10, PRO-16, PRO-17 / Daniel, Javier | Crear publicación con imagen, comentar y filtrar contenido | Pendiente de backends y frontend |
| Translate y Lex | PRO-18, PRO-19, PRO-42 / Javier, Daniel | Traducir a cuatro destinos y probar intención Lex | PRO-42 reporta 21/21 pruebas locales en Node; falta validar la ruta pública detrás del ALB |
| Chat en tiempo real | PRO-22, PRO-23 / equipo | Mensaje entre usuarios y persistencia/errores esperados | Pendiente |
| ALB con Node y Python | PRO-20, PRO-24 / Daniel, Javier, Guo | Ejecutar health checks, cambiar target y confirmar respuesta pública | Pendiente: no se entregó URL/DNS público del ALB; CloudFront `/api/v1/health` devuelve el SPA (`text/html`) |
| Failover de EC2 | PRO-25 / equipo | Detener cada EC2 por separado, validar continuidad y recuperar sin cambiar código | Pendiente de coordinación y ventana de prueba |
| Seguridad transversal | PRO-26 / Isai | Revisar 401/403, CORS, secretos fuera del repositorio y ausencia de BD local | Parcial: revisión documental; pruebas públicas pendientes |

## Registro de ejecución

| Caso | Responsable | Estado | Fecha | Evidencia | Falla / repetición |
| --- | --- | --- | --- | --- | --- |
| RDS disponible y aislado de Internet | Isai | Red VPC, migraciones, seed y `verify_schema.sql` aprobados; regla temporal revocada | 2026-10-18 | `docs/evidence/rds/report.md`, `docs/evidence/rds/images/vpc-rds-sg-validation.png` | Ejecutar consulta de aplicación Node/Python y reconciliar subnet group |
| User Pool y cliente sin secreto | Isai | Pool/cliente y CLI validados; integración API pendiente | 2026-10-15 | `docs/evidence/cognito/report.md`, `docs/evidence/cognito/images/cognito-cli-validation.png` | Requiere PRO-7/14 |
| Contrato de etiquetas e IAM | Isai | Contrato versionado; rol runtime más amplio que el mínimo | 2026-10-15 | `docs/evidence/rekognition-labels/report.md`, `docs/evidence/rekognition-labels/images/iam-role-policies-validation.png` | Coordinar reducción sin romper CompareFaces/Translate |
| Triggers faciales | Isai | 3 pruebas locales pasan; E2E pendiente | 2026-10-15 | `docs/evidence/cognito-facial/report.md` | Requiere S3 privado, upload y APIs |
| Upload de imágenes | Daniel | 9/9 pruebas locales; respuestas públicas 415/201 observadas | 2026-10-15 | `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images`, evidencia de PRO-11 | El endpoint no sustituye el API de negocio ni valida todavía el flujo facial completo |
| Frontend público HTTPS | Guo | Rutas `/login`, `/login/face` y `/register` cargan correctamente | 2026-10-18 | `https://d22yc8w9s5onhg.cloudfront.net/login` | `/api/v1/health` responde el `index.html`; falta origen ALB/API y variables `VITE_API_BASE_URL`/`VITE_UPLOAD_BASE_URL` |
| Node Translate/Lex | Javier | 21/21 pruebas locales reportadas | 2026-10-18 | `docs/api/node-language-bot.md` | No se marca como E2E hasta disponer de URL pública y límites de free tier |
| Suite local backend Python | PRO-13 / Javier | Ejecutar `python -m pytest backend-python/tests -q` dentro de `.venv` | 2026-10-15 | 114/114 pruebas aprobadas; no sustituye la prueba E2E en VPC | Requiere integración con EC2/ALB y RDS |
| Compilación backend Node.js | PRO-7/8/9/10 / Daniel | Ejecutar `npm ci --ignore-scripts` y `npm run build` en `backend-node` | 2026-10-15 | Compilación NestJS aprobada; la prueba pública y el arranque contra RDS siguen pendientes | `npm ci` reporta vulnerabilidades preexistentes; no se aplicó `audit fix` |
| Flujos públicos completos | Equipo | Bloqueado | — | Frontend HTTPS y upload disponibles; API de negocio aún no publicado | Requiere URL ALB, variables de frontend, PRO-7/14/21 y coordinación de PRO-31/42 |
| Failover Node/Python | Equipo | Bloqueado | — | — | Requiere ALB y dos EC2 disponibles |

## Bloqueos y riesgos abiertos

1. El frontend HTTPS y el upload de PRO-11 ya tienen endpoints verificables,
   pero la validación E2E depende de que los dueños publiquen el API de negocio
   detrás del ALB y entreguen sus variables/contratos finales. PRO-26 no
   reemplaza sus pruebas de aceptación.
2. RDS usa temporalmente el subnet group default porque la consola no ofreció
   `semisocial-g15-db-subnets`; debe resolverse antes de reconciliar IaC.
3. No se marcará un requisito como aprobado solo por existir una captura de
   configuración. Se requiere resultado funcional reproducible.
4. Las pruebas que puedan generar cargos (Rekognition, Translate, Lex o
   almacenamiento adicional) deben ejecutarse solo con autorización explícita
   y límites del free tier confirmados.
5. No se subieron credenciales, capturas faciales ni biometría. Las rutas
   públicas se probaron únicamente con solicitudes de lectura o payloads
   inválidos/efímeros para evitar cargos y exposición de datos.

## Handoff a PRO-27

La matriz queda lista para que cada integrante agregue su URL pública, fecha,
captura y resultado real. PRO-27 puede consolidar este reporte cuando se hayan
cerrado los bloqueos y repetido los casos fallidos; la edición final del manual
no forma parte de PRO-26.
