# Application Load Balancer de SemiSocial

Configuración reproducible de la entrada del API utilizada por **PRO-25**. Los
valores documentados corresponden al despliegue del grupo 15 en `us-east-1` y
no contienen credenciales ni secretos.

## Topología

```text
CloudFront API (HTTPS)
  -> ALB internet-facing (HTTP :80)
  -> target group de instancias (HTTP :3000)
     -> EC2 Node.js
     -> EC2 Python
```

| Recurso | Valor desplegado |
|---|---|
| ALB | `semisocial-g15-alb` |
| Target group | `semisocial-g15-api-tg` |
| Región | `us-east-1` |
| VPC | `vpc-07d71aba0ec5b2213` |
| Subred pública A | `subnet-00a44acf0a2087560` |
| Subred pública B | `subnet-061594793c9d5e5d7` |
| SG del ALB | `sg-02bfdb21497a1a4f2` |
| SG de backends | `sg-07d69b7d9901d499c` |
| Instancia Node.js | `i-05479ce4e0fa5b060` |
| Instancia Python | `i-0a3c4a8b108539d35` |

## Configuración del target group

- Tipo de destino: `instance`.
- Protocolo y puerto: `HTTP:3000`.
- Versión: HTTP/1.1.
- Health check: `GET /health` mediante el puerto de tráfico.
- Código esperado: `200`.
- Intervalo y timeout: 10 y 5 segundos.
- Umbrales healthy/unhealthy: 2/2.
- Deregistration delay: 30 segundos.
- Algoritmo: round robin, sin stickiness.

Las dos instancias deben responder `200` antes de ejecutar las pruebas de
distribución o failover. Un estado `running` de EC2 no sustituye el estado
`healthy` del target group.

## Configuración del ALB

- Esquema: `internet-facing`.
- Tipo de IP: IPv4.
- Listener: `HTTP:80`.
- Acción predeterminada: forward a `semisocial-g15-api-tg`.
- Idle timeout: 300 segundos para permitir upgrades WebSocket.
- Deletion protection: desactivada para el entorno académico.

El SG de backend admite TCP 3000 desde el SG del ALB, no desde
`0.0.0.0/0`. El SG del ALB admite HTTP 80 desde la prefix list administrada de
orígenes de CloudFront. RDS y los puertos administrativos no se publican.

## Reglas del listener: estado del 2026-10-26 (CloudTrail y `describe-rules`)

**Cambios manuales, fuera de CloudFormation y reversibles.** Hora de Guatemala (UTC-6); todos los eventos figuran con
el usuario compartido `CloudCinema-Admin`, de modo que **no consta quién borró la regla 10**.

| Local | UTC | Evento |
|---|---|---|
| 09:12 y 09:18 | 15:12 y 15:18 | `ModifyRule`: prueba del chat con la regla 10 recortada y restaurada |
| 10:54 | 16:54 | `DeleteRule`: se borró la regla de prioridad 10 |
| 10:57 | 16:57 | `DeleteTargetGroup`: `semisocial-g15-node-only-tg` |
| 15:13 | 21:13 | `CreateTargetGroup`: `semisocial-g15-python-only-tg` (HTTP 3000, health `/health`, solo la instancia de Python `i-0a3c4a8b108539d35`) |
| 15:15 | 21:15 | `CreateRule`: **prioridad 5**, `/api/v1/auth/face*` → `semisocial-g15-python-only-tg` |

Estado del listener HTTP:80 (`describe-rules`, ~15:20 hora local): **regla 5** hacia `semisocial-g15-python-only-tg` y
regla por defecto hacia `semisocial-g15-api-tg`; **no existe la regla 10**. Consecuencias:

- `/api/v1/auth/face*` va **solo a Python** (el almacén de retos del login facial está en memoria de un proceso). Con
  un solo destino no hay failover: si Python cae, el login facial deja de funcionar. Antes de la regla, 3 de 8
  peticiones de prueba llegaron a Python; después, 8 de 8.
- Desde las 10:54 chat, publicaciones y etiquetas (`/ws/*`, `/api/v1/conversations*`, `/api/v1/posts*`,
  `/api/v1/labels*`) se reparten entre Node y Python por `semisocial-g15-api-tg`. **No se verificó con tráfico real
  desde la página**: en las 4 horas siguientes no llegó ninguna conexión de chat a Python.
- Para recrear estas reglas desde el repositorio hay que añadirlas a la plantilla; hoy **no están versionadas**.

Detalle: [`docs/evidence/face-login/python-report.md`](../../docs/evidence/face-login/python-report.md).

## Regla por ruta (estado anterior, observada por CLI el 2026-10-24)

> **Superado:** la regla de prioridad 10 descrita aquí se borró el 2026-10-26 a las 10:54 (sección anterior).

Hecho observado por Javier con la CLI; no se verificó de nuevo al escribir esta
nota. Además de la acción predeterminada, el listener HTTP:80 tiene una regla de
**prioridad 10** que envía `/api/v1/posts*`, `/api/v1/labels*`,
`/api/v1/conversations*` y `/ws/*` al target group `semisocial-g15-node-only-tg`
(solo Node). Todo lo demás va a `semisocial-g15-api-tg` (Node y Python). Mientras
exista la regla, esas rutas no hacen failover a Python. Detalle y rutas que
alternan: `docs/api/python-posts.md` §10b. Pendiente: capturas del listener
(*Rules*) y los parámetros del grupo `node-only-tg`.

## CloudFront del API

| Campo | Valor |
|---|---|
| Distribución | `E3BPWGBX2XJ1C` |
| Dominio | `dxfjcvf5o1pes.cloudfront.net` |
| Origen | DNS de `semisocial-g15-alb` |
| Protocolo al origen | HTTP only, puerto 80 |
| Viewer policy | Redirect HTTP to HTTPS |
| Métodos | GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE |
| Cache policy | `CachingDisabled` |
| Origin request policy | `AllViewerExceptHostHeader` |

La distribución del API es independiente de la SPA para conservar códigos y
cuerpos JSON del backend y evitar que el fallback de React Router reemplace
errores del API por `index.html`.

## Verificación operativa

Después de autenticar AWS CLI, identificar el ARN del target group y consultar
los estados sin modificar recursos:

```powershell
$Region = "us-east-1"
$TargetGroupArn = aws elbv2 describe-target-groups `
  --region $Region `
  --names semisocial-g15-api-tg `
  --query "TargetGroups[0].TargetGroupArn" `
  --output text

aws elbv2 describe-target-health `
  --region $Region `
  --target-group-arn $TargetGroupArn `
  --query "TargetHealthDescriptions[].{Instance:Target.Id,Port:Target.Port,State:TargetHealth.State,Reason:TargetHealth.Reason}" `
  --output table

1..12 | ForEach-Object {
  curl.exe -s https://dxfjcvf5o1pes.cloudfront.net/health
}
```

## Secuencia controlada de failover

1. Confirmar ambos targets `healthy`.
2. Ejecutar 12 solicitudes y comprobar respuestas de Node y Python.
3. Detener una sola EC2 durante la ventana acordada.
4. Esperar a que el target deje de recibir tráfico y repetir 12 solicitudes.
5. Iniciar la instancia y esperar su recuperación como `healthy`.
6. Repetir con la otra EC2.
7. Restaurar las dos instancias y confirmar el estado final 2/2 `healthy`.

Durante la convergencia puede existir una respuesta transitoria 502/503/504.
Se debe registrar, esperar la exclusión del target y confirmar la continuidad
posterior. Nunca se detienen las dos instancias simultáneamente.

La prueba debe ejecutarse sin modificar código entre pasos. Para la evidencia
final se registran hora, target retirado, serie de respuestas, recuperación y
estado final; nunca tokens, contraseñas ni variables secretas.
