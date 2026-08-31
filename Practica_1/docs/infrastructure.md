# Infraestructura y operación

CloudCinema se despliega en `us-east-1`, separando presentación, API, datos e
imágenes. Este documento reúne la configuración que afecta al desarrollo y la
operación; las capturas históricas están en [`evidence/`](evidence/).

## Topología

```text
Navegador
   └── HTTPS ──> CloudFront
                    ├── contenido y rutas SPA ──> S3 web
                    └── /api/* ──> Application Load Balancer
                                      ├── EC2 Node.js :3000
                                      └── EC2 Python  :8000
                                             ├── RDS PostgreSQL :5432
                                             └── S3 de imágenes
```

CloudFront es la entrada pública HTTPS. El ALB es el único punto de entrada de
los backends y el navegador nunca consume directamente una dirección de EC2.

## Recursos y controles

| Recurso | Uso y control principal |
|---|---|
| CloudFront | Entrega el sitio mediante HTTPS, reescribe rutas de la SPA y envía `/api/*` al ALB. |
| S3 web | Publica el `dist/` del frontend estático. |
| Application Load Balancer | Distribuye la API entre las dos implementaciones y retira targets no saludables. |
| EC2 Node.js / EC2 Python | Ejecutan el mismo contrato HTTP. Node usa `3000` por defecto y Python `8000`. |
| RDS PostgreSQL 16 | Persiste usuarios, películas y listas; permanece privado. |
| S3 de imágenes | Guarda portadas y fotografías bajo `Fotos_Peliculas/` y `Fotos_Perfil/`. |
| IAM | Entrega credenciales temporales a cada EC2 mediante roles separados. |

## Entrada web y API

| Dato | Valor |
|---|---|
| Distribución CloudFront | `ENFJ0CP98RFBW` |
| Dominio público | `dztmn2ph7ok4j.cloudfront.net` |
| Bucket web | `practica1-web-g15` |
| Origen web | `practica1-web-g15.s3-website-us-east-1.amazonaws.com` |
| ALB | `cloudcinema-load-balancer` |
| DNS del ALB | `cloudcinema-load-balancer-1325750410.us-east-1.elb.amazonaws.com` |
| Target group | `cloudcinema-backends-tg` |
| Health check | `GET /salud`, código `200` |

El comportamiento predeterminado de CloudFront entrega el sitio de S3 y asocia
la función `cloudcinema-spa-routes` para resolver rutas de React Router. El
comportamiento `/api/*` usa el ALB, acepta todos los métodos del contrato,
deshabilita la caché y reenvía los encabezados mediante
`AllViewerExceptHostHeader`. El frontend usa `VITE_API_BASE_URL` vacío para
generar solicitudes relativas al mismo dominio.

RDS acepta TCP `5432` únicamente desde los security groups de las EC2. Las
EC2 aceptan tráfico de aplicación únicamente desde el security group del ALB.
La lectura de objetos S3 puede ser pública para mostrar imágenes, pero la
escritura requiere el rol de la instancia y no se permite `DeleteObject`.

## RDS PostgreSQL

| Dato | Valor |
|---|---|
| Instancia | `cloudcinema-g15` |
| Motor | PostgreSQL 16.14 |
| Clase | `db.t4g.micro` |
| Almacenamiento | 20 GiB `gp2`, cifrado, sin escalado automático |
| Host | `cloudcinema-g15.cmpaiquocfxf.us-east-1.rds.amazonaws.com` |
| Base de datos | `cloudcinema` |
| Puerto | `5432` |
| Acceso público | No |
| SSL | `verify-full` |
| Certificado CA | `/etc/ssl/certs/rds-global-bundle.pem` |

El host, las contraseñas y el secreto JWT se proporcionan fuera de Git. Los
usuarios de aplicación son `usuario_cloudcinema_node` y
`usuario_cloudcinema_python`. El usuario Python tiene permisos de
`SELECT/INSERT/UPDATE/DELETE` y uso de secuencias, pero no permisos de DDL:
el backend no debe crear ni alterar tablas.

## S3 e IAM

| Dato | Valor |
|---|---|
| Bucket | `practica1-images-g15` |
| Región | `us-east-1` |
| Prefijo de perfiles | `Fotos_Perfil/` |
| Prefijo de portadas | `Fotos_Peliculas/` |
| Cifrado | SSE-S3 |
| ACL | Deshabilitadas (`Bucket owner enforced`) |

Las claves de objeto se generan como `Fotos_Perfil/<uuid>.<ext>` o
`Fotos_Peliculas/<uuid>.<ext>`; nunca se utiliza el nombre original del
archivo. La URL pública de lectura se construye así:

```text
https://{BUCKET_IMAGENES}.s3.{REGION_AWS}.amazonaws.com/{clave}
```

| Backend | Perfil de instancia |
|---|---|
| Node.js | `CloudCinema-Node-S3-PRA3` |
| Python | `CloudCinema-Python-S3-PRA3` |

Los SDK deben usar la cadena de credenciales predeterminada de AWS. No se
guardan `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` ni archivos de credenciales
en el repositorio o en las EC2.

## Variables compartidas no secretas

| Variable | Valor |
|---|---|
| `REGION_AWS` | `us-east-1` |
| `BUCKET_IMAGENES` | `practica1-images-g15` |
| `PREFIJO_FOTOS_PERFIL` | `Fotos_Perfil/` |
| `PREFIJO_FOTOS_PELICULAS` | `Fotos_Peliculas/` |
| `BD_PUERTO` | `5432` |
| `BD_NOMBRE` | `cloudcinema` |
| `BD_SSL_MODO` | `verify-full` |
| `BD_CERTIFICADO_CA` | `/etc/ssl/certs/rds-global-bundle.pem` |

Las plantillas están en `config/.env.node.example` y
`config/.env.python.example`. Los archivos `.env` reales nunca se versionan.
Ambos backends deben recibir exactamente el mismo `SECRETO_JWT`.

## Despliegue de la API Python en EC2

La aplicación Python se ejecuta como `ubuntu` desde
`/opt/cloudcinema/Practica_1/api-python`, con Uvicorn en `0.0.0.0:8000`. El
servicio fija el puerto `8000`; si se cambia, hay que actualizar también el
target group y las reglas del security group.

El servicio y el script de despliegue son artefactos operativos versionados:

- `deploy/cloudcinema-python.service` define el servicio systemd.
- `deploy/deploy.sh` instala paquetes, crea `.venv`, instala
  `requirements.txt` y reinicia el servicio.
- `api-python/scripts/smoke_test_prod.py` ejecuta la prueba de extremo a
  extremo contra una URL indicada con `--base-url`.

Pasos mínimos en la EC2:

1. Clonar el repositorio con una deploy key generada dentro de la instancia;
   la clave privada nunca sale de ella.
2. Instalar el bundle CA de RDS en
   `/etc/ssl/certs/rds-global-bundle.pem`.
3. Crear `api-python/.env.python` directamente en el servidor, con permisos
   `600`, incluyendo `BD_HOST`, `BD_CONTRASENA`, `SECRETO_JWT` y la
   configuración del bucket. No transferir secretos por `scp` ni guardarlos en
   el repositorio.
4. Instalar el servicio y ejecutar `./deploy/deploy.sh` desde
   `Practica_1/`.
5. Verificar el proceso con `curl http://127.0.0.1:8000/salud` y comprobar el
   rol con `aws sts get-caller-identity`.

El script de humo crea datos de prueba y objetos S3. Debe ejecutarse solo con
autorización y sus registros deben limpiarse siguiendo las instrucciones que
imprime al finalizar.

## Application Load Balancer

| Target | Puerto | Health check |
|---|---:|---|
| EC2 Node.js | `3000` (por defecto) | `GET /salud` |
| EC2 Python | `8000` | `GET /salud` |

`/salud` no requiere autenticación, no consulta RDS ni S3 y es la única ruta
válida para un target group compartido. Node también expone `/health`, pero
Python no; por eso el ALB debe usar `/salud`.

Antes de habilitar el balanceo o probar failover:

- confirmar que Node y Python usan el mismo `SECRETO_JWT`;
- permitir en cada EC2 únicamente el puerto de su API desde el security group
  del ALB;
- permitir en RDS TCP `5432` desde los security groups de las EC2;
- verificar ambos targets con `/salud` y ejecutar pruebas autenticadas contra
  cada backend.

Nunca se debe abrir el puerto de la API a `0.0.0.0/0`.

## Operación y evidencia

1. Copiar la plantilla correspondiente de `config/` y completar secretos fuera
   del repositorio.
2. Adjuntar el perfil IAM correcto a cada EC2.
3. Ejecutar el esquema y los datos iniciales desde `database/`.
4. Probar lectura y carga de objetos en ambos prefijos de S3.
5. Confirmar que una operación no autorizada, como borrar un objeto, falla.
6. Consultar `GET /salud` a través del target group del ALB.

La evidencia está organizada por recurso:

- [RDS](evidence/rds/report.md)
- [S3 de imágenes](evidence/s3-images/report.md)
- [IAM](evidence/iam/report.md)
- [Datos iniciales](evidence/initial-data/report.md)
