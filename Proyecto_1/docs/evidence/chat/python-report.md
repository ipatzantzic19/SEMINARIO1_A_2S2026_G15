# Reporte de evidencia: chat en tiempo real (API Python)

* **Tickets:** PRO-16 (chat de Python) y PRO-17 (reinicio de la EC2 de Python)
* **Módulo:** `backend-python` (FastAPI / uvicorn)
* **Documentación técnica:** [`docs/api/python-chat.md`](../../api/python-chat.md); contrato compartido: [`docs/api/chat.md`](../../api/chat.md)
* **Referencia Node:** [`node-report.md`](node-report.md)
* **Fecha de las pruebas:** 2026-10-26 (todas las horas en UTC)

Los usuarios aparecen como **usuario A** y **usuario B**; no se registran correos, tokens ni contraseñas.

## 1. Resumen

| Qué | Resultado (2026-10-26) |
|---|---|
| La EC2 de Python vuelve sola tras un reinicio de la máquina | **Hecho** (§3) |
| La rama del chat se despliega en la EC2 y el servicio arranca con el listener `LISTEN` activo | **Hecho** (§4) |
| Prueba cruzada Python ↔ Node con RDS real, en los dos sentidos (mensaje, acuse e historial) | **Hecho**, con `scripts/chat_smoke.py` ejecutado **dentro de la EC2 de Python** (§5) |
| Una conexión de navegador llegó a `/ws/chat` de Python y Python registró dos mensajes enviados desde la página | **Hecho, de forma breve** (~15:14 a 15:17 UTC) y con la regla del ALB cambiada **temporalmente** (§7); sin captura ni registro del contenido de las ventanas |
| Ningún log del servicio contiene `token=` | **Hecho** (§6) |
| El chat de la página lo atiende Python de forma permanente | **No**: la regla de prioridad 10 volvió a los cuatro patrones y `/ws/*` y `/api/v1/conversations*` van otra vez solo a `semisocial-g15-node-only-tg` (§8) |

La prueba cruzada (§5) **no** pasó por el ALB hacia Python: el usuario A habló con la API Python por `127.0.0.1:3000` (dentro
de la instancia) y el usuario B con Node por el origen público de CloudFront. Solo la prueba de §7 hizo llegar un navegador a
Python a través del balanceador.

## 2. Entorno

| Dato | Valor |
|---|---|
| Instancia | `i-0a3c4a8b108539d35` (`semisocial-g15-python-1`), cuenta `581117996165`, `us-east-1` |
| Rol de la instancia | `semisocial-g15-backend-role` |
| Acceso | Session Manager (sin SSH) |
| Servicio | `semisocial-python` (systemd), puerto 3000 |
| Antes del chat | `develop`, commit `5e3a280` (`alineacion-contrato-resend`) |
| Rama desplegada | `javiervelasquez39/pro-16-python-chat`, commit `f38e0f3` («docs: add Python chat contract notes») |
| Estado al final de las pruebas | **La instancia sigue en esa rama y commit** (`f38e0f3`); `develop` **no** está desplegado |
| Dependencia nueva | `websockets==16.1.1` |
| Origen público usado por B | `https://dxfjcvf5o1pes.cloudfront.net` (CloudFront → ALB → Node) |

## 3. Reinicio de la EC2 de Python (PRO-17)

Reinicio desde la consola de EC2 («Reboot instance»). Sesión nueva de Session Manager el 2026-10-26 a las 14:39 UTC, con el
servicio aún en el commit `5e3a280` (versión de `develop` anterior al chat):

| Comprobación | Resultado |
|---|---|
| `uptime -p` | `up 3 minutes` |
| `systemctl is-active semisocial-python` | `active` |
| `systemctl is-enabled semisocial-python` | `enabled` |
| `GET http://127.0.0.1:3000/health` | `200` `{"status":"ok","service":"python","version":"1.0.0"}` |

El servicio volvió solo tras reiniciar la máquina. **Lo que no cubre:** que el puerto 3000 no responda desde Internet
(ver §9).

## 4. Despliegue de la rama del chat

| Comprobación | Resultado |
|---|---|
| `bootstrap.sh` | Instaló `websockets==16.1.1` y terminó con «OK: http://127.0.0.1:3000/health responde 200» |
| `python -c "import websockets"` en el venv | `16.1.1` |
| `journalctl -u semisocial-python` | `chat.listener_ready` al arrancar (14:40:13 UTC); sin `Traceback` |
| `GET /api/v1/conversations/<uuid>/messages` sin token | `401 UNAUTHENTICATED` (la ruta existe; antes de este despliegue respondía `501`) |

Una línea `connection rejected (400 Bad Request)` del journal **no es un fallo de la aplicación**: la provocó una prueba manual
con `curl` con una cabecera `Sec-WebSocket-Key` inválida. No se usa como evidencia.

## 5. Prueba cruzada con `scripts/chat_smoke.py`

Ejecutada **dentro de la EC2 de Python** entre las 14:40 y las 14:48 UTC, en una sesión de Session Manager:

```bash
cd /opt/semisocial/src/Proyecto_1/backend-python
/opt/semisocial/venv/bin/python scripts/chat_smoke.py \
    --public-origin https://dxfjcvf5o1pes.cloudfront.net \
    --email-a "$EA" --email-b "$EB"       # los correos se leen con `read -p` y no se registran aquí
```

El usuario A inicia sesión en la API Python (`127.0.0.1:3000`) y se conecta a su WebSocket; el usuario B inicia sesión en el
origen público (que atiende Node) y se conecta al WebSocket de Node. Las contraseñas se piden con `getpass` (no se
muestran). El script solo imprime OK o FALLO y la latencia; no imprime tokens ni el texto de los mensajes.

| # | Paso | Resultado | Latencia |
|---|---|---|---|
| 1 | Login de A en la API Python | OK | 768 ms |
| 2 | Login de B en el origen público (Node) | OK | 393 ms |
| 3 | Obtener `userId` de A y B (`GET /me`) | OK | — |
| 4 | A conecta al WebSocket de Python | OK | 11 ms |
| 5 | B conecta al WebSocket de Node | OK | 24 ms |
| 6 | Python → Node (A→B): el destinatario recibe `message:new` | OK | 16 ms |
| 7 | Python → Node (A→B): el emisor recibe `message:ack` | OK | 15 ms |
| 8 | Node → Python (B→A): el destinatario recibe `message:new` | OK | 7 ms |
| 9 | Node → Python (B→A): el emisor recibe `message:ack` | OK | 7 ms |
| 10 | Historial en RDS visible por Python (≥ 2 mensajes) | OK | — |
| 11 | Historial en RDS visible por Node (≥ 2 mensajes) | OK | — |
| | **RESULTADO** | **OK** | |

Las latencias se midieron desde la EC2 (Python por la interfaz local, Node por CloudFront); no representan la latencia de un
navegador. Los mensajes de la prueba quedaron guardados en el historial entre A y B.

**Qué respalda (con RDS real):** la difusión por `LISTEN/NOTIFY` entre las dos instancias (Python y Node) en **ambos
sentidos**; el `INSERT` con `pg_notify`, el acuse (`message:ack`) y el historial desde Python; el WebSocket de Node por el
origen público; y que el historial REST de Python lee de RDS.

## 6. Control de seguridad: el token en la URL

El token viaja en la query de `/ws/chat`. Sobre el journal de `semisocial-python` (`grep -c "token="`):

| Momento | Coincidencias de `token=` |
|---|---|
| Antes de la prueba cruzada (§5) | **0** |
| Después de la prueba cruzada | **0** |
| Después de la prueba desde la página (§7), sobre los últimos 60 minutos del journal | **0** |

El log de uvicorn de esa prueba muestra la ruta sin query string: `"WebSocket /ws/chat" [accepted]`.

## 7. Prueba desde la página con la regla del ALB cambiada temporalmente (~15:14 a 15:17 UTC)

**Objetivo:** comprobar que una conexión de navegador llega al chat de Python. Para ello la regla de prioridad 10 del listener
HTTP:80 de `semisocial-g15-alb` se redujo **temporalmente** a dos patrones, de modo que `/ws/*` y
`/api/v1/conversations*` cayeron en la acción predeterminada (`semisocial-g15-api-tg`, con Node y Python). Los dos destinos de
ese grupo estaban `healthy`.

**Lecturas de `aws elbv2 describe-rules` sobre el listener, en orden:**

| Lectura | Patrones de la regla de prioridad 10 | Comentario |
|---|---|---|
| (a) antes | `/api/v1/posts*`, `/api/v1/labels*`, `/api/v1/conversations*`, `/ws/*` | Estado documentado |
| (b) durante la prueba | solo `/api/v1/posts*`, `/api/v1/labels*` | Cambio temporal |
| (c) lectura **final** | los cuatro patrones otra vez | Regla restaurada |

**Registro de Python durante la prueba** (journal filtrado por `ws/chat` y `chat.`; sin tokens ni contenido de mensajes):

| Hora (UTC) | Logger | Evento |
|---|---|---|
| 15:14:14.211 | `uvicorn.error` | `172.31.7.148:4616 - "WebSocket /ws/chat" [accepted]` |
| 15:14:14.218 | `semisocial.chat` | `chat.connected` |
| 15:14:14.281 | `semisocial.chat` | `chat.disconnected` |
| 15:14:15.043 | `uvicorn.error` | `172.31.7.148:4606 - "WebSocket /ws/chat" [accepted]` |
| 15:14:15.053 | `semisocial.chat` | `chat.connected` |
| 15:14:26.908 | `semisocial.users` | `chat.message_sent` |
| 15:17:29.298 | `semisocial.users` | `chat.message_sent` |

**Qué respalda:**

1. Con la regla en dos patrones, una conexión de un navegador llegó a `/ws/chat` de Python (origen `172.31.7.148`, una IP
   privada de la VPC, coherente con el balanceador; no se comprobó a qué interfaz pertenece).
2. Python registró **dos** mensajes enviados desde la página (`chat.message_sent`).
3. El log de uvicorn muestra la ruta sin query string y el token no aparece en el journal (§6).
4. La conexión no se cerró entre los dos mensajes, separados por unos 3 minutos (por debajo del idle timeout de 300 s del
   ALB, que **no** se probó).
5. Una primera conexión se cerró 63 ms después de abrirse y se abrió otra unos 0,8 s más tarde. **Causa no investigada.**

**Qué no respalda:** la persona que hizo la prueba la describe como correcta, pero **no hay captura ni registro del contenido
de las ventanas**, no se confirmó que el historial coincidiera tras recargar y solo se esperaron unos 3 minutos. Tampoco hay
mensajes cruzados entre dos ventanas con registro.

## 8. Estado final de la regla del ALB

La lectura final (c) de §7 muestra **otra vez los cuatro patrones**: `/api/v1/posts*`, `/api/v1/labels*`,
`/api/v1/conversations*` y `/ws/*` (la captura de la consola de la regla restaurada muestra además la acción «Reenviar al grupo
de destino `semisocial-g15-node-only-tg`: 1 (100 %)»). Por tanto **el chat que usa la página va de nuevo solo a
`semisocial-g15-node-only-tg`** (solo Node), igual que las publicaciones y las etiquetas, y el failover de esas rutas hacia
Python no existe mientras la regla siga así. Es el estado descrito en `infra/alb/README.md` y en `docs/api/python-posts.md`
§10b, que no se modificaron.

La instancia de Python sigue en la rama `javiervelasquez39/pro-16-python-chat` (commit `f38e0f3`); `develop` no está
desplegado.

## 9. No verificado

- Reconexión del listener tras un corte de RDS.
- Idle timeout de 300 s del ALB y de CloudFront en conexiones WebSocket largas.
- Historial coincidente tras recargar la página en la prueba de §7.
- Mensajes cruzados entre dos ventanas, con registro, en la prueba de §7.
- Idempotencia por `clientMessageId`: **no implementada** (Node tampoco; ver `python-chat.md` §9.2).
- Chat de la página repartido entre ambas instancias de forma permanente (la regla quedó en cuatro patrones).
- Que el puerto 3000 de la EC2 no responda desde Internet.
- La causa de la primera conexión de §7, que se cerró 63 ms después de abrirse.
