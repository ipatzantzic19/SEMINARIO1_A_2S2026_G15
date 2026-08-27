# Infraestructura para el ALB (PRA-20) — ficha directa para Persona 4

**Última actualización:** 2026-08-27.

## ⚠ ADVERTENCIA CRÍTICA — `SECRETO_JWT` no coincide hoy entre Node y Python

**El secreto JWT de las dos instancias probablemente NO es el mismo ahora mismo.** El backend Python fue rotado a un valor real durante esta sesión (verificado en vivo momentos antes de escribir este documento: un token firmado con el literal `default_secret` ya es rechazado por `GET /api/v1/perfil` en la instancia real de Python — `401 ERROR_AUTENTICACION`). El backend Node.js **probablemente sigue usando el valor por defecto inseguro `'default_secret'`**, hardcodeado en `api-node/src/config/configuration.ts:18` (`jwtSecret: process.env.SECRETO_JWT || 'default_secret'`) si nadie configuró la variable de entorno en su EC2 — documentado como discrepancia #7 en [`../api-contract.md`](../api-contract.md).

**No pude confirmar de forma independiente cuál es el secreto real de Node en este momento** — un intento de verificarlo contra la instancia real de producción (con una petición de solo lectura, sin crear ninguna cuenta) fue bloqueado por una política de seguridad de esta sesión, precisamente porque forjar un token de autenticación contra infraestructura de otra persona del equipo requiere su autorización explícita, no la mía. Persona 3 (yo) o el propietario de esa EC2 deben confirmarlo directamente.

**Mientras `SECRETO_JWT` no sea idéntico en ambas instancias, la prueba de failover de PRA-20 va a fallar en cualquier escenario donde un token emitido por un backend se intente validar contra el otro** — que es exactamente lo que pasa cuando el ALB redirige la siguiente petición del mismo usuario al servidor contrario tras un failover. **Esto debe resolverse antes de ejecutar esa prueba — no es opcional ni puede quedar pendiente para después.**

---

## Instancia Python (EC2 #2 — PRA-15)

| Dato | Valor | Fuente |
|---|---|---|
| Instance ID | `i-091c3d0e84fe82907` | Reportado directamente por Persona 3; no existe en ningún documento del repo (hueco ya señalado en el inventario de documentación) |
| IP pública | `54.91.86.90` | Confirmada en vivo (`GET /salud` → `200`, momentos antes de escribir este documento) |
| Puerto de la app | `8000` | Coincide con `deploy/cloudcinema-python.service:12` (`--port 8000`) y con la respuesta real observada |
| Security Group | `sg-0be0cc30c55bb82c4` (`cloudcinema-python-sg`) | Reportado directamente por Persona 3; no existe en ningún documento del repo |
| Reglas actuales del SG | TCP 22 (SSH) y TCP 8000, ambas restringidas a una IP administrativa individual — **temporal** | Reportado por Persona 3 |
| Health check | `GET /salud` — sin autenticación, sin prefijo `/api/v1` | Confirmado en vivo, código en `app/salud/router.py` |
| Rol IAM adjunto | `CloudCinema-Python-S3-PRA3` | Confirmado en vivo — el registro de un usuario de prueba subió realmente una imagen a S3 sin ninguna credencial local, solo con este rol |

## Instancia Node.js (EC2 #1 — PRA-10)

**PRA-10 sigue en `Backlog` en Linear** (no `Done`) y no existe ningún `docs/pra-10/` en el repo — todo lo siguiente proviene de lo que reportaste tú, no de un documento propio de Persona 2 ni de verificación mía contra el repo:

| Dato | Valor | Fuente |
|---|---|---|
| IP pública | `54.162.122.66` | Reportado — confirmado en vivo por mí ahora mismo (`GET /salud` → `200`) |
| Puerto de la app | `3000` | Reportado. Coincide con el valor por defecto de `api-node/src/config/configuration.ts:2` (`process.env.PORT \|\| '3000'`), pero eso solo confirma que *no* se sobreescribió esa variable — no hay documento de Persona 2 que declare `3000` como el puerto elegido a propósito |
| Health check | `GET /salud` — confirmado funcional contra producción vía Postman (por ti) | También existe `GET /health` como alias no documentado en el diseño (`api-node/src/salud/health.controller.ts`) — **usa `/salud`** para el health check del target group, así ambos backends comparten la misma configuración sin excepciones. Python no tiene `/health`. |
| Security Group | **No reportado, no documentado** | Hueco — falta el ID |
| Reglas actuales del SG | **No reportado, no documentado** | Hueco |
| Rol IAM adjunto | `CloudCinema-Node-S3-PRA3` (existe, verificado en PRA-4 según `docs/pra-4/EVIDENCIAS_PRA_4_IAM.md`) — **no confirmado que esté realmente adjunto a esta EC2**, a diferencia del de Python | `EVIDENCIAS_PRA_4_IAM.md` documenta que el rol existe; nadie ha documentado ni verificado en vivo que esté asociado a esta instancia |

---

## Checklist — qué debe cambiar cuando el ALB exista

- [ ] **Crítico, bloqueante:** confirmar y sincronizar `SECRETO_JWT` entre Node y Python (ver advertencia arriba) — sin esto, la prueba de failover no es válida.
- [ ] SG de Python (`sg-0be0cc30c55bb82c4`): cambiar la regla de entrada TCP 8000 de "IP administrativa individual" a "origen = Security Group del ALB" (nunca `0.0.0.0/0`).
- [ ] SG de Python: revisar si la regla TCP 22 (SSH) debe seguir abierta a esa IP administrativa o restringirse más — no depende del ALB, pero es buen momento para revisarla.
- [ ] SG de Node: **presumiblemente necesita el mismo cambio** (puerto 3000 restringido al SG del ALB) — no se puede confirmar el estado actual porque el SG de Node no está documentado ni reportado; hay que pedírselo directamente a Persona 2.
- [ ] Configurar el health check del target group con la ruta `GET /salud` para **ambos** targets (no `/health` para Node) — así ambos backends comparten exactamente la misma configuración sin una excepción por backend.
- [ ] Confirmar que PRA-10 (EC2 de Node) pase de `Backlog` a `Done` en Linear con su propia evidencia documentada — hoy no hay ningún `docs/pra-10/`, a diferencia de `docs/pra-15/` para Python.
