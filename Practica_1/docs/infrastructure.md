# Infraestructura y configuración

CloudCinema se despliega en `us-east-1` separando presentación, API, datos e
imágenes. La infraestructura vigente se resume aquí; las capturas de cada
recurso se conservan en [`docs/evidence/`](evidence/).

## Topología

```text
Navegador
   ├── frontend estático ──> S3 web
   └── API ──> Application Load Balancer
                    ├── EC2 Node.js
                    └── EC2 Python
                           ├── RDS PostgreSQL
                           └── S3 de imágenes
```

El ALB es el único punto de entrada de la API y comprueba `GET /salud` en cada
target. El navegador nunca consume una dirección de EC2 directamente.

## Recursos y controles

| Recurso | Uso y control principal |
|---|---|
| S3 web | Publica el `dist/` del frontend estático. |
| Application Load Balancer | Distribuye la API entre las dos implementaciones y retira targets no saludables. |
| EC2 Node.js / EC2 Python | Ejecutan el mismo contrato HTTP. |
| RDS PostgreSQL 16 | Persiste usuarios, películas y listas; permanece privado. |
| S3 de imágenes | Guarda portadas y fotografías bajo `Fotos_Peliculas/` y `Fotos_Perfil/`. |
| IAM | Entrega credenciales temporales a cada EC2 mediante roles separados. |

RDS acepta TCP `5432` únicamente desde los security groups de las EC2. Las
EC2 aceptan tráfico de aplicación desde el security group del ALB. La lectura
de objetos S3 puede ser pública para mostrar imágenes, pero escritura y
eliminación requieren el rol de la instancia.

## Valores compartidos no secretos

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

Los usuarios de base de datos son `usuario_cloudcinema_node` y
`usuario_cloudcinema_python`. Las contraseñas, `BD_HOST` y `SECRETO_JWT` se
inyectan por fuera de Git; ambos backends deben recibir exactamente el mismo
secreto JWT.

## Roles IAM

| Backend | Perfil de instancia |
|---|---|
| Node.js | `CloudCinema-Node-S3-PRA3` |
| Python | `CloudCinema-Python-S3-PRA3` |

Los roles pueden listar los prefijos autorizados, leer y cargar objetos, pero
no borrar objetos ni acceder a otros buckets. Los SDK deben usar la cadena de
credenciales predeterminada de AWS, nunca access keys almacenadas en archivos.

## Operación y verificación

1. Copiar la plantilla correspondiente de `Practica_1/config/` y completar los
   secretos fuera del repositorio.
2. Adjuntar el perfil IAM correcto a cada EC2.
3. Conectar a PostgreSQL con SSL y el usuario de aplicación correspondiente.
4. Ejecutar el esquema y los datos iniciales desde `database/`.
5. Probar lectura y carga de objetos en los dos prefijos de S3.
6. Confirmar que una operación no autorizada, como borrar un objeto, falla.
7. Consultar `GET /salud` a través del target group del ALB.

La URL de visualización de una imagen se construye a partir de su clave:

```text
https://{BUCKET_IMAGENES}.s3.{REGION_AWS}.amazonaws.com/{clave}
```

La evidencia histórica está organizada por recurso:

- [RDS](evidence/rds/report.md)
- [S3 de imágenes](evidence/s3-images/report.md)
- [IAM](evidence/iam/report.md)
- [Datos iniciales](evidence/initial-data/report.md)
