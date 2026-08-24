# Evidencias paso a paso — PRA-2 Amazon RDS

**Incidencia:** PRA-2 — Crear y configurar Amazon RDS  
**Región:** `us-east-1`  
**Motor:** PostgreSQL 16  
**Instancia:** `cloudcinema-g15`

## Propósito

Este documento registra visualmente la creación y configuración de Amazon RDS para CloudCinema. El procedimiento fue reconstruido desde cero y las capturas corresponden a la consola real de AWS.

Las contraseñas, tokens y llaves no se incluyen en las evidencias. Los identificadores técnicos, nombres de recursos y valores de configuración se conservan porque forman parte de la documentación académica.

## 0. Estado previo y respaldo de seguridad

Antes de reconstruir se verificó el recurso existente y se creó la instantánea `cloudcinema-g15-pre-reconstruccion-20260824`.

### Security group previo

![Security group previo](img/pra-2/00-estado-previo-security-group.jpg)

### Configuración previa de RDS

![Configuración previa de RDS](img/pra-2/01-estado-previo-rds-configuracion.jpg)

### Conectividad previa de RDS

![Conectividad previa de RDS](img/pra-2/02-estado-previo-rds-conectividad.jpg)

### Snapshot manual de recuperación

La instantánea se conservó antes de eliminar la instancia anterior y AWS confirmó el estado `Disponible`.

![Snapshot manual de recuperación](img/pra-2/02b-snapshot-recuperacion.jpg)

## 1. Creación del security group de RDS

Se crea primero un security group dedicado. De esta manera RDS puede seleccionar un recurso existente y no necesita crear reglas temporales basadas en la IP pública del equipo.

### Datos básicos

![Formulario del security group](img/pra-2/03-security-group-formulario.jpg)

### Sin reglas de entrada iniciales y salida predeterminada

Mientras las EC2 de las Personas 2 y 3 todavía no existan, el security group no permite conexiones entrantes. Se conserva la salida predeterminada de AWS; esa regla no abre el puerto PostgreSQL hacia RDS.

![Security group sin entradas](img/pra-2/04-security-group-sin-entradas.jpg)

### Security group creado

![Security group creado](img/pra-2/05-security-group-creado.jpg)

## 2. Motor y método de creación

Se selecciona PostgreSQL y el método de configuración completa para controlar red, costo, respaldo y seguridad.

![Motor y método de creación](img/pra-2/06-motor-y-metodo.jpg)

## 3. Plantilla y disponibilidad

Se utiliza la plantilla de capa gratuita y una sola zona de disponibilidad para evitar recursos redundantes con costo adicional.

![Plantilla y disponibilidad](img/pra-2/07-plantilla-y-disponibilidad.jpg)

## 4. Credenciales administrativas

El usuario maestro es `admincloudcinema`. La contraseña se genera automáticamente, se guarda fuera de Git y no aparece en capturas. El identificador `cloudcinema-g15` se comprueba en la captura de aprovisionamiento.

![Identificador y credenciales](img/pra-2/08-identificador-y-credenciales.jpg)

## 5. Almacenamiento y conexión con EC2

Se configuran 20 GiB de SSD de propósito general, se desactiva el escalado automático y no se vincula una EC2 durante la creación. La clase `db.t4g.micro` se comprueba en la verificación final.

![Clase y almacenamiento](img/pra-2/09-clase-y-almacenamiento.jpg)

## 6. Conectividad privada

RDS utiliza la VPC predeterminada, no tiene acceso público y se asocia únicamente con el security group `rds-cloudcinema-g15` creado en el paso anterior.

![Conectividad privada](img/pra-2/10-conectividad-privada.jpg)

## 7. Supervisión

Se conserva Database Insights estándar y se desactiva la monitorización mejorada con costo adicional.

![Supervisión](img/pra-2/11-supervision.jpg)

## 8. Mantenimiento y protección

Se habilitan las actualizaciones automáticas de versiones secundarias y la protección contra eliminación. El cifrado, la base inicial `cloudcinema` y los respaldos se comprueban en las vistas finales de AWS.

![Configuración adicional](img/pra-2/12-configuracion-adicional.jpg)

## 9. Etiquetas

Se agregan las etiquetas `Proyecto=CloudCinema` e `Incidencia=PRA-2` para identificar el propósito y el ticket responsable del recurso.

![Etiquetas](img/pra-2/13-etiquetas.jpg)

## 10. Revisión previa a la creación

Antes de crear se vuelve a comprobar el mantenimiento automático y la protección contra eliminación. La configuración completa queda registrada en el conjunto de capturas anteriores y se verifica nuevamente cuando la instancia está disponible.

![Revisión antes de crear](img/pra-2/14-revision-antes-de-crear.jpg)

## 11. Aprovisionamiento

AWS crea la instancia y sus componentes asociados. La consola ofrece una sola ventana para consultar la contraseña generada; esa información se guarda en un gestor de contraseñas y no se captura.

![RDS en creación](img/pra-2/15-rds-en-creacion.jpg)

## 12. Verificación final

### Instancia disponible

![RDS disponible](img/pra-2/16-rds-disponible.jpg)

### Motor, almacenamiento y seguridad

![Configuración final](img/pra-2/17-configuracion-final.jpg)

La vista adicional confirma Single-AZ, escalado automático desactivado y protección contra eliminación habilitada.

![Almacenamiento y protección final](img/pra-2/17b-almacenamiento-proteccion-final.jpg)

### Red privada

![Conectividad final](img/pra-2/18-conectividad-final.jpg)

### Respaldos

![Respaldos finales](img/pra-2/19-respaldos-finales.jpg)

### Security group sin entradas públicas

![Security group final](img/pra-2/20-security-group-final.jpg)

### Valores comprobados en AWS

| Configuración | Resultado |
|---|---|
| Estado | Disponible |
| Motor | PostgreSQL 16.14 |
| Clase | `db.t4g.micro` |
| Base inicial | `cloudcinema` |
| Usuario maestro | `admincloudcinema` |
| Despliegue | Single-AZ |
| Almacenamiento | 20 GiB `gp2`, cifrado, sin escalado automático |
| Acceso público | No |
| Security group | `rds-cloudcinema-g15` (`sg-0e034b66e1c196572`), sin entradas |
| Copias automatizadas | Habilitadas, retención de 1 día |
| Protección contra eliminación | Habilitada |
| Supervisión | Database Insights estándar; monitorización mejorada desactivada |

## Trabajo pendiente para completar PRA-2

- Guardar la contraseña administrativa generada en un gestor de contraseñas; no compartirla por GitHub ni Linear.
- Recibir los security groups de EC2 de Personas 2 y 3.
- Autorizar TCP 5432 únicamente desde esos dos security groups.
- Ejecutar `database/schema.sql` y `database/permisos_aplicacion.sql` desde una EC2 autorizada.
- Ejecutar `database/verificar_rds.sql`.
- Probar los usuarios separados de Node.js y Python.
