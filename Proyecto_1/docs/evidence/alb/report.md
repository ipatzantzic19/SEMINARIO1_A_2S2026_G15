# Balanceo de carga y entrada pública del API

**Proyecto:** SemiSocial · Proyecto final · Grupo 15  
**Ticket:** PRO-25 — Validar failover de EC2 mediante el ALB  
**Fecha de implementación:** 22 de octubre de 2026  
**Estado:** infraestructura desplegada y operativa; prueba de failover pendiente

## 1. Objetivo

Publicar los backends de SemiSocial mediante un Application Load Balancer
(ALB), centralizar sus comprobaciones de salud, retirar el acceso público
directo al puerto de aplicación y exponer el API con HTTPS mediante una
distribución CloudFront independiente de la SPA.

La separación entre la distribución web y la distribución del API evita que
las respuestas de React Router conviertan errores HTTP del backend en
`index.html`. Así, el frontend conserva los códigos y cuerpos JSON reales.

## 2. Arquitectura implementada

```text
Navegador
   │ HTTPS / WSS
   ▼
CloudFront API · dxfjcvf5o1pes.cloudfront.net
   │ HTTP :80
   ▼
Application Load Balancer · semisocial-g15-alb
   │ HTTP :3000
   ▼
Target group · semisocial-g15-api-tg
   ├── EC2 Node.js · i-05479ce4e0fa5b060
   └── EC2 Python  · i-0a3c4a8b108539d35
          │
          ▼
     Amazon RDS PostgreSQL
```

CloudFront termina HTTPS y reenvía solicitudes sin caché hacia el ALB. El ALB
solo envía tráfico a targets que superan `GET /health`. Ambos backends utilizan
la misma base de datos para que la persistencia no dependa de la instancia.

## 3. Inventario definitivo

| Recurso | Identificador o valor | Estado verificado |
|---|---|---|
| Cuenta AWS | `581117996165` | Activa |
| Región | `us-east-1` | Activa |
| VPC | `vpc-07d71aba0ec5b2213` | Asociada |
| SG del ALB | `sg-02bfdb21497a1a4f2` | Configurado |
| SG de backends | `sg-07d69b7d9901d499c` | Configurado |
| EC2 Node.js | `i-05479ce4e0fa5b060` | `healthy` |
| EC2 Python | `i-0a3c4a8b108539d35` | `unhealthy` por health check |
| Target group | `semisocial-g15-api-tg` | Activo |
| ALB | `semisocial-g15-alb` | Activo |
| DNS del ALB | `semisocial-g15-alb-327553020.us-east-1.elb.amazonaws.com` | Responde HTTP |
| CloudFront API | `E3BPWGBX2XJ1C` | `Deployed` y habilitada |
| Dominio HTTPS del API | `dxfjcvf5o1pes.cloudfront.net` | Responde HTTPS |

## 4. Target group y comprobaciones de salud

El target group se creó para instancias sobre HTTP/1.1 y puerto 3000. La ruta
`/health` determina qué backend puede recibir tráfico.

| Parámetro | Configuración |
|---|---|
| Tipo de target | Instances |
| Protocolo y puerto | HTTP :3000 |
| Ruta de salud | `/health` |
| Puerto de salud | Traffic port |
| Código esperado | `200` |
| Umbrales healthy / unhealthy | 2 / 2 |
| Timeout / intervalo | 5 s / 10 s |
| Deregistration delay | 30 s |
| Algoritmo | Round robin |
| Stickiness | Desactivada |

Las dos instancias quedaron registradas. La validación remota confirmó a Node
como `healthy`; Python permanece `unhealthy` porque su runtime todavía no
satisface el health check. El ALB no le envía tráfico mientras conserve ese
estado.

![Configuración básica del target group](images/target-group-basic-configuration.png)

![Health check del target group](images/target-group-health-check.png)

![Registro de las instancias](images/target-group-registered-instances.png)

![Atributos finales del target group](images/target-group-final-attributes.png)

## 5. Application Load Balancer

El ALB se desplegó como `internet-facing`, IPv4, en dos subredes públicas de la
VPC del proyecto.

| Campo | Valor |
|---|---|
| Nombre | `semisocial-g15-alb` |
| VPC | `vpc-07d71aba0ec5b2213` |
| Subred us-east-1a | `subnet-00a44acf0a2087560` |
| Subred us-east-1b | `subnet-061594793c9d5e5d7` |
| Listener | HTTP :80 |
| Acción | Forward a `semisocial-g15-api-tg` |
| Security group | `sg-02bfdb21497a1a4f2` |
| Idle timeout | 300 segundos |
| Deletion protection | Desactivada |
| Desync mitigation | Defensive |

El tiempo de espera de 300 segundos evita cerrar prematuramente conexiones
WebSocket. No se configuró afinidad porque el estado persistente se comparte en
RDS y el contexto de servicios administrados permanece fuera de la EC2.

![Configuración de red del ALB](images/alb-network-mapping.png)

![Security group y listener](images/alb-security-and-listener.png)

![ALB activo con su DNS público](images/alb-active-overview.png)

![Atributos finales del ALB](images/alb-final-attributes.png)

## 6. CloudFront exclusivo para el API

Se creó la distribución `semisocial-api-g15` con el ALB como origen. No se
reutilizó la distribución de la SPA y no se habilitó WAF para evitar costos
adicionales no requeridos por el proyecto.

| Campo | Valor |
|---|---|
| Distribution ID | `E3BPWGBX2XJ1C` |
| Dominio | `dxfjcvf5o1pes.cloudfront.net` |
| Origen | DNS de `semisocial-g15-alb` |
| Protocolo al origen | HTTP only, puerto 80 |
| Viewer protocol policy | Redirect HTTP to HTTPS |
| Métodos | GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE |
| Cache policy | `CachingDisabled` |
| Origin request policy | `AllViewerExceptHostHeader` |
| Origin Shield | Desactivado |
| WAF | No configurado |
| Logging | Desactivado |

`AllViewerExceptHostHeader` reenvía autorización, cookies y query strings sin
enviar al ALB el `Host` de CloudFront. La política sin caché evita respuestas
obsoletas o el intercambio accidental de respuestas autenticadas.

![ALB seleccionado como origen](images/cloudfront-alb-origin.png)

![Origen HTTP y conexión](images/cloudfront-http-origin-settings.png)

![Métodos y redirección HTTPS](images/cloudfront-protocol-and-methods.png)

![Políticas de caché y reenvío](images/cloudfront-cache-and-origin-policies.png)

![CloudFront sin WAF](images/cloudfront-without-waf.png)

![Resumen antes de crear la distribución](images/cloudfront-creation-review.png)

![Distribución desplegada](images/cloudfront-deployed-overview.png)

## 7. Seguridad de red

La exposición directa de las EC2 se retiró después de comprobar la ruta por el
ALB y CloudFront:

- el SG de backends permite TCP 3000 únicamente desde
  `sg-02bfdb21497a1a4f2`;
- ya no existe una regla `3000` desde `0.0.0.0/0`;
- el SG del ALB permite HTTP 80 únicamente desde la prefix list administrada
  `pl-3b927c52`, correspondiente a los orígenes de CloudFront;
- RDS, secretos, tokens y puertos administrativos no se exponen públicamente.

Así, el tráfico web debe seguir CloudFront → ALB → EC2 y no puede alcanzar el
servicio mediante la IP pública de una instancia.

## 8. Validaciones ejecutadas

### 8.1 Respuesta directa del ALB

`GET /health` mediante el DNS del ALB devolvió HTTP 200:

```json
{
  "status": "ok",
  "service": "node",
  "version": "1.0.0"
}
```

Una ruta inexistente devolvió HTTP 404 con el contrato JSON del backend, no
HTML de la SPA.

![Health 200 y error JSON mediante el ALB](images/alb-health-and-json-error.png)

### 8.2 Respuesta HTTPS mediante CloudFront

Se repitieron ambas solicitudes contra la distribución pública:

```text
GET https://dxfjcvf5o1pes.cloudfront.net/health
→ HTTP 200
→ {"status":"ok","service":"node","version":"1.0.0"}

GET https://dxfjcvf5o1pes.cloudfront.net/api/v1/ruta-inexistente
→ HTTP 404
→ Content-Type: application/json
→ code: NOT_FOUND
```

Esto confirma que HTTPS llega al backend, el API no se almacena en caché y los
errores conservan su estado y representación JSON.

### 8.3 Matriz de resultados

| Caso | Resultado |
|---|---|
| Node mediante health check | Aprobado · `healthy` |
| Health mediante ALB | Aprobado · HTTP 200 |
| Error del API mediante ALB | Aprobado · HTTP 404 JSON |
| Health mediante CloudFront | Aprobado · HTTPS 200 |
| Error del API mediante CloudFront | Aprobado · HTTPS 404 JSON |
| Caché desactivada para el API | Aprobado |
| Puerto 3000 cerrado al público | Aprobado |
| ALB restringido a CloudFront | Aprobado |
| Compatibilidad del transporte WSS | Configurada |
| Failover Node → Python y Python → Node | **Pendiente hasta que Python esté `healthy`** |

## 9. Prueba restante de failover

La única validación restante de PRO-25 es la alternancia real entre dos targets
saludables. Debe realizarse después de que Python responda 200 en `/health` y el
target group la marque como `healthy`:

1. confirmar ambos targets como `healthy`;
2. realizar varias solicitudes y observar ambos runtimes;
3. detener temporalmente Node y comprobar continuidad mediante Python;
4. restaurar Node y esperar su recuperación automática;
5. detener temporalmente Python y comprobar continuidad mediante Node;
6. restaurar Python y conservar ambos targets saludables.

No debe detenerse Node mientras sea el único target saludable, porque eso
interrumpiría completamente el API público.

## 10. Resultado

El ALB, target group, CloudFront y los security groups quedaron desplegados y
verificados. El frontend dispone de un único origen HTTPS para el API y las EC2
dejaron de exponer directamente el puerto 3000. La infraestructura está lista
para distribuir tráfico entre ambos runtimes cuando Python supere su health
check; entonces solo faltará ejecutar y registrar la prueba de failover.
