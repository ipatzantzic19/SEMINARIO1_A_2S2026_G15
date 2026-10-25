# Validación operativa del ALB — 25/10/2026

Ejecución de solo lectura realizada el **25 de octubre de 2026 a las
17:08 UTC-06:00** contra la cuenta `581117996165` y la región `us-east-1`.
No se imprimieron tokens, contraseñas ni parámetros secretos.

## Estado de infraestructura

- `semisocial-g15-alb`: `active`, internet-facing, IPv4.
- Listener: HTTP 80 con forward a `semisocial-g15-api-tg`.
- Target group: HTTP 3000, health check `GET /health`, matcher `200`.
- Node `i-05479ce4e0fa5b060`: `running` y `healthy` en puerto 3000.
- Python `i-0a3c4a8b108539d35`: `running` y `healthy` en puerto 3000.
- Algoritmo: `round_robin`; stickiness desactivada.
- Deregistration delay: 30 segundos.
- Idle timeout del ALB: 300 segundos.

La consulta se realizó con:

```powershell
$TargetGroupArn = aws elbv2 describe-target-groups `
  --region us-east-1 `
  --names semisocial-g15-api-tg `
  --query "TargetGroups[0].TargetGroupArn" `
  --output text

aws elbv2 describe-target-health `
  --region us-east-1 `
  --target-group-arn $TargetGroupArn `
  --query "TargetHealthDescriptions[].{Instance:Target.Id,Port:Target.Port,State:TargetHealth.State}" `
  --output table
```

Resultado equivalente:

```text
i-05479ce4e0fa5b060  3000  healthy
i-0a3c4a8b108539d35  3000  healthy
```

## Distribución vigente

Se realizaron 12 conexiones HTTPS independientes mediante CloudFront:

```text
01 python  200
02 node    200
03 node    200
04 python  200
05 node    200
06 python  200
07 python  200
08 node    200
09 node    200
10 python  200
11 node    200
12 python  200
```

Resultado: **12/12 HTTP 200, 6 Node y 6 Python**. Esto confirma que CloudFront
alcanza el ALB y que el target group distribuye tráfico entre ambos runtimes.

## Ruta protegida representativa

Se ejecutaron seis solicitudes a `GET /api/v1/me` sin credenciales. Todas
respondieron `401`, con el esquema común:

```json
{
  "code": "UNAUTHENTICATED",
  "message": "Mensaje legible",
  "requestId": "uuid",
  "details": null
}
```

Los dos textos observados fueron `Autenticación requerida.` y `Cabecera
Authorization con formato Bearer <token> requerida.`. El código, estado y
estructura coinciden, pero el texto humano todavía no es idéntico entre los
runtimes. No se utilizaron credenciales para esta comprobación.

## Red

- El SG del backend admite TCP 3000 exclusivamente desde el SG del ALB.
- El SG del ALB admite HTTP 80 desde la prefix list administrada de orígenes
  CloudFront `pl-3b927c52`.
- No existe ingreso público `0.0.0.0/0` al puerto 3000.
- CloudFront `E3BPWGBX2XJ1C` permanece habilitada, usa el ALB como origen HTTP y
  redirige viewers a HTTPS.

## Failover ejecutado por el equipo

La ejecución coordinada del 25/10/2026 registrada en Linear para PRO-26/PRO-31
obtuvo:

- Node fuera de servicio: Python sostuvo **12/12 HTTP 200** después de la
  convergencia.
- Python fuera de servicio: se observó un `504` transitorio mientras el target
  group convergía y después Node sostuvo **12/12 HTTP 200**.
- Node fue corregido para ejecutar `dist/src/main.js` mediante un servicio
  systemd activo y habilitado.
- Python fue restaurado y el target group terminó con los dos targets healthy.

La comprobación de solo lectura de este documento confirmó posteriormente el
estado final 2/2 healthy y la distribución 6/6, sin repetir la detención de las
instancias.
