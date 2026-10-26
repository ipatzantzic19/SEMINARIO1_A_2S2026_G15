# Evidencia de validación integral - PRO-26

Estado: **E2E real de Cognito, upload, persistencia autenticada y rutas
protegidas aprobado; se detectó deriva de contrato en la respuesta desplegada
de publicaciones. ALB y failover en ambos sentidos verificados.**

Fecha de actualización: 25 de octubre de 2026. Responsable de coordinación:
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
| Arquitectura, contrato y modelo común | PRO-1 / Isai | Comparar contrato, rutas y modelo con el despliegue | `docs/api/contract.md`; contrato alineado localmente y E2E público ejecutado; el runtime desplegado aún devuelve aliases legacy en `POST /posts` |
| Backend Python y contrato OpenAPI | PRO-13/14 / Javier, Isai | Ejecutar la suite de contrato/configuración y verificar que el arranque falla cerrado sin variables críticas | `backend-python/tests/`; suite local **641 pruebas aprobadas**; integración pública pendiente |
| IAM mínimo, VPC y SG | PRO-4 / Isai | Revisar acceso permitido/denegado y ausencia de permisos amplios | `docs/evidence/iam/report.md`, `network/report.md`; evidencia de configuración, prueba conjunta pendiente |
| RDS PostgreSQL y esquema | PRO-2 / Isai | Conectar desde backend autorizado, aplicar migraciones y ejecutar `database/tests/verify_schema.sql` | `docs/evidence/rds/report.md`, `docs/evidence/network/vpc-peering-20261019.txt`; red VPC, peering, migraciones, seed y verificación aprobados. Node y Python autenticaron contra RDS desde sus EC2 usando el parámetro `SecureString` sin exponer la contraseña; falta probar las rutas de negocio detrás del API/ALB. El subnet group homónimo queda como riesgo de IaC, no como bloqueo de conectividad |
| S3 de imágenes | PRO-3 / Isai | Subir/leer objeto con prefijo autorizado y rechazar escritura anónima | `docs/evidence/s3-images/report.md`; prueba funcional conjunta pendiente |
| Registro, confirmación y recuperación | PRO-5 + PRO-7/14 / Isai, Daniel, Javier | Registrar, confirmar código, iniciar sesión, recuperar y rechazar no confirmado | `docs/evidence/cognito/report.md`; recuperación y login reales aprobados contra CloudFront |
| Perfil completo y foto obligatoria | PRO-11, PRO-21 / Daniel, Guo | Completar foto con JWT, verificar `profileComplete` y bloquear feed incompleto | Upload 201, `complete-profile` 200 y persistencia de `/me` aprobados; ver `docs/evidence/API-gateway/reporte.md` |
| Login facial y contrato de etiquetas | PRO-12, PRO-31 / Isai | Comparar rostro válido/no válido y claims; no emitir JWT propio | Upload/profile E2E aprobado; la comparación facial real queda fuera de esta ejecución y no se invocó Rekognition adicional |
| Usuarios y amistades | PRO-8, PRO-15 / Daniel, Javier | Solicitar, aceptar, rechazar y consultar feed de amigos | Pendiente de ambos backends |
| Publicaciones, comentarios y filtros | PRO-9, PRO-10, PRO-16, PRO-17 / Daniel, Javier | Crear publicación con imagen, comentar y filtrar contenido | Upload real `201` y `POST /posts` autenticado `201` aprobados; el despliegue devolvió además `id`, `authorId`, `imageKey` y `labelDetails`, por lo que aún falta publicar la alineación de contrato |
| Translate y Lex | PRO-18, PRO-19, PRO-42 / Javier, Daniel | Traducir a cuatro destinos y probar intención Lex | PRO-42 reporta 21/21 pruebas locales en Node; falta validar la ruta pública detrás del ALB |
| Chat en tiempo real | PRO-22, PRO-23 / equipo | Mensaje entre usuarios y persistencia/errores esperados | Backend Node.js y transporte/frontend WebSocket integrados en `develop`; suites locales aprobadas. Falta prueba cruzada Node↔Python detrás del ALB |
| ALB con Node y Python | PRO-20, PRO-24 / Daniel, Javier, Guo | Ejecutar health checks, cambiar target y confirmar respuesta pública | Parcialmente aprobado: `semisocial-g15-api-tg` muestra ambos targets `healthy`; 12 llamadas a `https://dxfjcvf5o1pes.cloudfront.net/health` devolvieron HTTP 200 (6 Node, 6 Python). La salud es `/health`; la base de negocio es `/api/v1`. |
| Failover de EC2 | PRO-25 / equipo | Detener cada EC2 por separado, validar continuidad y recuperar sin cambiar código | Parcial aprobado: Node → Python sostuvo 12/12 HTTP 200 tras convergencia; después de corregir el servicio Node, Python → Node sostuvo 12/12 HTTP 200 adicionales. Ambos targets quedaron `healthy` al restaurar Python |
| Seguridad transversal | PRO-26 / Isai | Revisar 401/403, CORS, secretos fuera del repositorio y ausencia de BD local | Aprobado para rutas probadas: CORS `OPTIONS /health` 200; `/me` y `/posts` sin credencial o con Bearer inválido 401; Bearer válido 200; secretos no registrados |

## Registro de ejecución

| Caso | Responsable | Estado | Fecha | Evidencia | Falla / repetición |
| --- | --- | --- | --- | --- | --- |
| RDS disponible y aislado de Internet | Isai | Red VPC, migraciones, seed, `verify_schema.sql` y consultas Node/Python desde VPC aprobados; reglas temporales revocadas | 2026-10-18 | `docs/evidence/rds/report.md`, `docs/evidence/rds/images/vpc-rds-sg-validation.png` | Subnet group homónimo está en otra VPC; documentar IaC si el equipo exige un grupo propio |
| User Pool y cliente sin secreto | Isai | Pool/cliente y CLI revalidados; `ALLOW_CUSTOM_AUTH` habilitado conservando password/SRP/refresh; integración API y bandeja de prueba pendientes | 2026-10-19 | `docs/evidence/cognito/report.md`, `docs/evidence/cognito/images/cognito-cli-validation-live.jpg` | Requiere triggers desplegados, correo de prueba autorizado y coordinación PRO-7/14/21/31 |
| Contrato de etiquetas e IAM | Isai | Contrato versionado; política `semisocial-g15-ai-invoke` reducida a `DetectLabels` y `TranslateText` en `us-east-1` | 2026-10-25 | `docs/evidence/rekognition-labels/report.md`; captura visual de IAM | `CompareFaces` se retiró del rol EC2; falta validar runtime real de etiquetas/persistencia |
| Triggers faciales | Isai | 4 pruebas locales pasan; triggers asociados; E2E pendiente | 2026-10-19 | `docs/evidence/cognito-facial/report.md` | `CUSTOM_AUTH` alcanza `CreateAuthChallenge`; falta `custom:face_reference_key` del flujo de upload |
| Revalidación de triggers faciales | Isai | Ejecutar `npm test` en `lambdas/cognito-facial` | 2026-10-22 | **4/4 pruebas Node aprobadas**; no se usó AWS ni biometría real | E2E continúa pendiente de S3 privado, upload, Cognito y APIs |
| Upload de imágenes | Daniel | 9/9 pruebas locales; respuestas públicas 415/201 observadas | 2026-10-15 | `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images`, evidencia de PRO-11 | El endpoint no sustituye el API de negocio ni valida todavía el flujo facial completo |
| Contratos Cognito/S3/Rekognition | Isai | Ejecutar las suites locales de triggers, upload y etiquetas sin invocar AWS | 2026-10-22 | Cognito facial **4/4**, image-upload **9/9** y `rekognition.service.spec.ts` **4/4**; validan captura privada por challenge, copia de referencia, prefijos autorizados, CORS, JWT, checksum, normalización y `NoSuchKey` | Son pruebas con dobles/stubs locales; falta ejecutar el flujo autenticado real con la bandeja autorizada y el API público |
| Frontend público HTTPS | Guo | Rutas `/login`, `/login/face` y `/register` cargan correctamente | 2026-10-24 | `https://d22yc8w9s5onhg.cloudfront.net/login`; `VITE_API_BASE_URL=https://dxfjcvf5o1pes.cloudfront.net`; `VITE_UPLOAD_BASE_URL=https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com`; CORS de `/health` verificado con `OPTIONS` HTTP 200 | SPA y endpoints públicos entregados; falta validar el flujo autenticado completo |
| Node Translate/Lex | Javier | 21/21 pruebas locales reportadas | 2026-10-18 | `docs/api/node-language-bot.md` | No se marca como E2E hasta disponer de URL pública y límites de free tier |
| Suite local backend Python | PRO-13 / Javier | Ejecutar `python -m pytest -rA` dentro de `backend-python/.venv` | 2026-10-22 | **641/641 pruebas aprobadas**; la suite usa dobles locales y no invoca servicios AWS reales | No sustituye la prueba E2E: requiere integración con EC2/ALB y RDS |
| Compilación backend Node.js | PRO-7/8/9/10 / Daniel | Ejecutar `npm ci --ignore-scripts` y `npm run build` en `backend-node` | 2026-10-15 | Compilación NestJS aprobada; la prueba pública y el arranque contra RDS siguen pendientes | `npm ci` reporta vulnerabilidades preexistentes; no se aplicó `audit fix` |
| Revalidación local backend Node.js | Isai | Ejecutar `npm run build` y la suite de contrato de Rekognition en `backend-node` desde `develop` actualizado | 2026-10-19 | Compilación NestJS aprobada nuevamente; `rekognition.service.spec.ts` pasa **4/4** con doble local y sin invocar AWS | La validación pública, persistencia RDS y E2E siguen pendientes; la suite usa un archivo de localStorage temporal por Node 25 |
| Chat Node.js integrado | Isai / Daniel | Compilar el gateway WebSocket y los servicios de persistencia/notificación desde `develop` actualizado | 2026-10-20 | `npm run build` aprobado; contrato y reporte en `docs/api/chat.md` y `docs/evidence/chat/node-report.md`; commit remoto `793704e` | Falta ejecutar el intercambio Node↔Python con RDS, ALB y failover; no se creó infraestructura ni se usó AWS |
| Chat frontend integrado | Isai / Guo | Ejecutar la suite del frontend y compilar el transporte WebSocket desde `develop` actualizado | 2026-10-25 | `pnpm test`: **19 archivos, 89 pruebas aprobadas**; `pnpm typecheck` aprobado y el flujo de chat/feed/traducción quedó cubierto localmente; cambios remotos en `0df4693` | La prueba real con ALB/RDS y el intercambio Node↔Python siguen pendientes; no se usó AWS |
| Revalidación local backend Python | Isai / Javier | Instalar `requirements-dev.txt` en `.venv` y ejecutar `python -m pytest -rA` desde `backend-python` | 2026-10-22 | **641/641 pruebas aprobadas** después de instalar `boto3/botocore`; no se invocó AWS durante la suite | La validación local no sustituye la prueba funcional autenticada en la EC2/ALB |
| Revalidación remota backend Python | Isai / Javier | Instalar Python 3.11 paralelo, crear `.venv311`, instalar requisitos y ejecutar pytest en la EC2 | 2026-10-22 | Python `3.11.16`, `fastapi 0.143.1` y requisitos instalados en `/opt/semisocial/.venv311`; la suite llegó al 100% y RDS `5432` respondió | Falta arrancar la aplicación con su contrato final, persistencia desde una ruta de negocio y exposición mediante ALB |
| Preparación remota backend Node | Isai / Daniel | Clonar `develop` en la EC2 Node, instalar las dependencias declaradas y compilar NestJS sin tocar secretos | 2026-10-22 | Run Command `3c053aea-1d56-4f58-ba43-6d880f319e1e` terminó **Correcto** en `i-05479ce4e0fa5b060`: checkout en `/opt/semisocial-node`, `npm ci --ignore-scripts` y `npm run build` finalizaron con código 0; Node `v22.23.3`/npm `10.9.9` | El runtime quedó preparado; faltan contrato de variables de aplicación, arranque del servicio y API detrás del ALB |
| Autenticación técnica Node contra RDS | Isai / Daniel | Leer el secreto aprobado en SSM en memoria y consultar `SELECT 1` y `public.users` desde la EC2 Node | 2026-10-22 | Run Command `44f48474-d02f-4e38-962d-8f4b68b32dda` terminó **Correcto** en `i-05479ce4e0fa5b060`; instaló AWS CLI con `apt`, obtuvo el `SecureString` sin imprimirlo ni guardarlo, y reportó `AWS_CLI=/usr/bin/aws`, `RDS_AUTH_SELECT=1`, `RDS_USERS_TABLE=users` | La prueba confirma credenciales/red/driver, pero no sustituye login Cognito ni persistencia de una ruta HTTP detrás del ALB |
| Autenticación técnica Python contra RDS | Isai / Javier | Leer el secreto aprobado en SSM y consultar `SELECT 1` y `public.users` desde la EC2 Python | 2026-10-22 | Run Command `259bf4ce-d8bc-456f-ad0c-c097a881e737` terminó **Correcto** en `i-0a3c4a8b108539d35`; `SSM_PARAMETER_ACCESS=OK`, `RDS_AUTH_SELECT=1`, `RDS_USERS_TABLE=users`, sin imprimir la contraseña | La prueba confirma credenciales/red/driver, pero no sustituye login Cognito ni persistencia de una ruta HTTP detrás del ALB |
| Estado remoto de EC2 y SSM | Isai / Daniel, Javier | Consultar Fleet Manager, validar runtimes y probar autenticación contra RDS | 2026-10-22 | Fleet Manager reporta Online a Node `i-05479ce4e0fa5b060` y Python `i-0a3c4a8b108539d35`. Node `v22.23.3`/npm `10.9.9`, Python `3.11.16` con `fastapi 0.143.1`; ambas consultas autenticadas devolvieron `SELECT 1` y `public.users` | Falta probar Cognito, persistencia de una ruta de negocio y rutas públicas detrás del ALB; no se modificó el ALB ni se invocaron servicios AWS de pago |
| Flujos públicos completos | Isai | Aprobado para Cognito/upload/perfil/rutas protegidas | 2026-10-25 | Login 200; upload 201; `complete-profile` 200; `/me` y `/posts` 401 sin token/200 con token | El E2E facial y las superficies sociales adicionales no forman parte de esta ejecución |
| Reconciliación Cognito → RDS | Isai | Corregir usuario existente en Cognito sin fila de aplicación y repetir el E2E | 2026-10-25 | Se creó la fila de aplicación usando el `sub` de Cognito; `/me`, `PATCH /me` y lectura posterior confirmaron persistencia | No se registraron contraseña, código, JWT, correo completo ni fotografía en el repositorio |
| Ruteo Node del ALB | Isai | Resolver 503 de `/api/v1/posts` y repetir rutas protegidas | 2026-10-25 | La regla de prioridad 10 apuntaba a `semisocial-g15-node-only-tg` sin destinos; se registró la EC2 Node en puerto 3000 y quedó `healthy`; `/posts` pasó a 401/200 según credencial | Captura visual del estado del target group queda en la sesión de consola AWS y la evidencia de configuración del ALB permanece en `docs/evidence/alb/` |
| Arranque persistente de Node | Isai / Daniel | Aprobado | 2026-10-25 | Run Command `2c545a2f-a8d5-4e05-8102-8f298cb408e1`: `systemd enabled`, proceso en `*:3000`, RDS conectado y `/health` devolvió `status=ok`; se corrigió `dist/main` → `dist/src/main.js` | No se registraron secretos ni se expusieron variables; el servicio quedó habilitado al arranque |
| Failover Node/Python | Equipo | Parcial aprobado | 2026-10-25 | Node detenido → Python sostuvo 12/12 HTTP 200 tras convergencia. Python detenido → hubo un `504` inicial de convergencia y las 12 solicitudes siguientes devolvieron HTTP 200 por CloudFront. Captura final del target group: 2 destinos `healthy`, 0 `unhealthy` | La continuidad quedó validada; falta repetir con una cuenta Cognito autorizada y comprobar persistencia completa de las rutas de negocio |
| Alineación de contrato Node/Python | Isai / Daniel / Javier | Ajustar respuestas públicas al OpenAPI común y verificar pruebas del backend Node | 2026-10-25 | Node: build, 15 pruebas unitarias y E2E **69/69**; Python: suite completa aprobada; frontend: **89/89** y typecheck; `HeadObject`, códigos comunes, `Post`, `Comment`, `PostPage`, `Label[]`, `body`, cursor común y ausencia de `Todos/general` alineados localmente. E2E público: login/me/posts/labels `200`, upload `201`, creación de publicación `201` | El runtime desplegado aún responde con aliases legacy en `POST /posts`; falta desplegar la alineación y repetir la prueba cruzada Node/Python |

## Bloqueos y riesgos abiertos

1. El E2E autorizado de Cognito/upload/perfil y las rutas protegidas probadas ya
   está aprobado. El login facial real, las publicaciones con Rekognition,
   amistades, chat y demás superficies sociales requieren sus propios casos de
   aceptación y no se marcan como aprobados por esta prueba.
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
6. El desfase horario de la consola AWS quedó corregido y SSM ya permite
   ejecutar comandos. La EC2 Python conserva Python 3.9 del sistema y usa
   Python 3.11 en paralelo dentro de `/opt/semisocial/.venv311`; no se
   reemplazó el intérprete del sistema.
7. La preparación remota de Node, la autenticación técnica contra RDS y el
   servicio persistente ya están completas en `/opt/semisocial-node`. El
   secreto se obtiene desde SSM en memoria y se conserva únicamente en el
   archivo root-only de runtime de la instancia; no se registró su valor. En
   el entorno local, `npm test -- --runInBand` queda limitado por
   `SecurityError` de localStorage del runtime de Jest; esto no invalida el
   build remoto correcto ni las pruebas específicas de Rekognition ya
   registradas (4/4 con dobles locales).

## Handoff a PRO-27

La matriz queda lista para que cada integrante agregue su URL pública, fecha,
captura y resultado real. PRO-27 puede consolidar este reporte cuando se hayan
cerrado los bloqueos y repetido los casos fallidos; la edición final del manual
no forma parte de PRO-26.
