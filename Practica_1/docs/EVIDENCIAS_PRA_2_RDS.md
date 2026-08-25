# Evidencias paso a paso — PRA-2 Amazon RDS

**Incidencia:** PRA-2 — Crear y configurar Amazon RDS  
**Región:** `us-east-1`  
**Motor:** PostgreSQL 16  
**Identificador de la instancia:** `cloudcinema-g15`

## Propósito

Este documento presenta, en orden, la creación y configuración de la base de datos administrada de CloudCinema en Amazon RDS. La secuencia cubre la red, el motor, el almacenamiento, la seguridad, el aprovisionamiento y la validación privada del esquema.

Las contraseñas, tokens y llaves no se incluyen en las evidencias. Los nombres de recursos y valores técnicos se documentan porque forman parte de la entrega académica.

## 1. Crear el security group para RDS

Primero se crea un security group dedicado para la base de datos. Esto permite controlar el acceso al puerto PostgreSQL desde los security groups de los servidores autorizados, sin depender de direcciones IP públicas.

### 1.1 Definir los datos básicos

Se selecciona la VPC de trabajo y se asigna el nombre `rds-cloudcinema-g15` con una descripción que identifica su propósito.

![Formulario del security group](img/pra-2/03-security-group-formulario.jpg)

### 1.2 Mantener el grupo sin entradas iniciales

Mientras todavía no se tienen los security groups de las dos EC2, no se agregan reglas de entrada. Se conserva únicamente la salida predeterminada de AWS.

![Security group sin entradas](img/pra-2/04-security-group-sin-entradas.jpg)

### 1.3 Confirmar la creación

Se verifica que el security group fue creado correctamente y queda disponible para asociarlo a RDS.

![Security group creado](img/pra-2/05-security-group-creado.jpg)

## 2. Seleccionar el motor y el método de creación

En Amazon RDS se selecciona PostgreSQL y la opción de configuración completa. Esta opción permite revisar manualmente la red, la capacidad, el almacenamiento, los respaldos y la protección de la instancia.

![Motor y método de creación](img/pra-2/06-motor-y-metodo.jpg)

## 3. Elegir plantilla y disponibilidad

Se utiliza la plantilla de capa gratuita y una implementación Single-AZ. La práctica no necesita alta disponibilidad para esta fase y la selección evita recursos redundantes con costo adicional.

![Plantilla y disponibilidad](img/pra-2/07-plantilla-y-disponibilidad.jpg)

## 4. Configurar el identificador y las credenciales

Se define el identificador `cloudcinema-g15` y el usuario maestro `admincloudcinema`. La contraseña se genera y se guarda fuera del repositorio, sin incluirla en capturas ni archivos versionados.

![Identificador y credenciales](img/pra-2/08-identificador-y-credenciales.jpg)

## 5. Configurar la clase y el almacenamiento

Se selecciona la clase `db.t4g.micro`, se asignan 20 GiB de almacenamiento SSD de propósito general y se desactiva el escalado automático para mantener controlado el consumo de créditos.

![Clase y almacenamiento](img/pra-2/09-clase-y-almacenamiento.jpg)

## 6. Configurar la conectividad privada

Se utiliza la VPC predeterminada de `us-east-1`, se mantiene desactivado el acceso público y se asocia el security group `rds-cloudcinema-g15`. La base de datos queda preparada para recibir tráfico únicamente desde recursos autorizados dentro de la VPC.

![Conectividad privada](img/pra-2/10-conectividad-privada.jpg)

## 7. Configurar la supervisión

Se conserva Database Insights estándar y se deja desactivada la monitorización mejorada, ya que no es necesaria para la práctica y puede generar cargos adicionales.

![Supervisión](img/pra-2/11-supervision.jpg)

## 8. Configurar mantenimiento, cifrado y protección

Se habilitan las actualizaciones automáticas de versiones secundarias, el cifrado y la protección contra eliminación. También se define la base inicial `cloudcinema` y la configuración de respaldos.

![Configuración adicional](img/pra-2/12-configuracion-adicional.jpg)

## 9. Agregar etiquetas

Se agregan las etiquetas `Proyecto=CloudCinema` e `Incidencia=PRA-2` para identificar el recurso y relacionarlo con el ticket correspondiente.

![Etiquetas](img/pra-2/13-etiquetas.jpg)

## 10. Revisar la configuración antes de crear

Antes de iniciar el aprovisionamiento se revisan nuevamente el motor, la clase, el almacenamiento, la red, el mantenimiento y la protección contra eliminación.

![Revisión antes de crear](img/pra-2/14-revision-antes-de-crear.jpg)

## 11. Iniciar el aprovisionamiento

Se confirma la creación de la instancia. AWS inicia el aprovisionamiento de RDS y muestra el estado de la operación en la consola.

![RDS en creación](img/pra-2/15-rds-en-creacion.jpg)

## 12. Confirmar que RDS está disponible

Cuando finaliza el aprovisionamiento, la instancia cambia al estado `Disponible` y puede consultarse desde la consola.

![RDS disponible](img/pra-2/16-rds-disponible.jpg)

## 13. Verificar la configuración final

### 13.1 Motor, clase y almacenamiento

Se verifica PostgreSQL 16.14, la clase `db.t4g.micro`, los 20 GiB de almacenamiento y el cifrado.

![Configuración final](img/pra-2/17-configuracion-final.jpg)

### 13.2 Protección y escalado

Se confirma que la protección contra eliminación está habilitada y que el escalado automático de almacenamiento permanece desactivado.

![Almacenamiento y protección final](img/pra-2/17b-almacenamiento-proteccion-final.jpg)

### 13.3 Red y acceso público

Se confirma que RDS utiliza la VPC definida, no tiene acceso público y está asociado al security group de la base de datos.

![Conectividad final](img/pra-2/18-conectividad-final.jpg)

### 13.4 Respaldos

Se verifica que los respaldos automatizados están habilitados con una retención de un día.

![Respaldos finales](img/pra-2/19-respaldos-finales.jpg)

### 13.5 Security group de RDS

El security group de RDS permanece sin entradas públicas. Las reglas de TCP 5432 se agregarán únicamente para los security groups de las EC2 autorizadas.

![Security group final](img/pra-2/20-security-group-final.jpg)

## 14. Preparar una conexión privada para aplicar el esquema

Como las EC2 de PRA-10 y PRA-15 todavía no están disponibles, se utiliza temporalmente un entorno de AWS CloudShell dentro de la misma VPC y subred. Esta alternativa permite aplicar el esquema sin habilitar el acceso público de RDS.

### 14.1 Crear el security group temporal

Se crea `cloudshell-rds-admin-g15` para autorizar temporalmente la conexión administrativa desde CloudShell.

![Formulario del security group temporal](img/pra-2/21-security-group-cloudshell-formulario.jpg)

![Reglas del security group temporal](img/pra-2/22-security-group-cloudshell-reglas.jpg)

![Security group temporal creado](img/pra-2/23-security-group-cloudshell-creado.jpg)

### 14.2 Autorizar temporalmente el puerto PostgreSQL

Se agrega TCP 5432 en el security group de RDS únicamente desde `cloudshell-rds-admin-g15`.

![Regla temporal de RDS](img/pra-2/24-regla-rds-desde-cloudshell.jpg)

![Regla temporal guardada](img/pra-2/25-regla-rds-cloudshell-guardada.jpg)

### 14.3 Crear el entorno CloudShell dentro de la VPC

Se configura el entorno CloudShell con la VPC, subred y security group temporal seleccionados.

![Formulario del entorno CloudShell VPC](img/pra-2/26-cloudshell-vpc-formulario.jpg)

![Entorno CloudShell VPC en creación](img/pra-2/27-cloudshell-vpc-creando.jpg)

![Entorno CloudShell VPC listo](img/pra-2/28-cloudshell-vpc-listo.jpg)

## 15. Aplicar y verificar el esquema PostgreSQL

Desde CloudShell se ejecutan los scripts del repositorio para crear las tablas, índices, funciones, triggers, comentarios y permisos de aplicación. La contraseña se introduce directamente en la terminal y no se almacena en archivos.

![Solicitud de contraseña de PostgreSQL](img/pra-2/29-psql-solicita-contrasena.jpg)

### 15.1 Primera verificación

La primera ejecución confirmó la conexión, PostgreSQL 16.14 y TLS 1.3. También mostró que `information_schema.triggers` puede devolver una fila por evento cuando un trigger atiende `INSERT OR UPDATE`; por eso el conteo inicial no representaba tres nombres de trigger distintos.

![Resultado inicial de la verificación](img/pra-2/30-verificacion-conteo-triggers.jpg)

### 15.2 Verificación corregida

Se ajusta la consulta de verificación para contar nombres distintos de triggers y se ejecuta nuevamente. El resultado confirma las tablas `usuarios`, `peliculas` y `lista_reproduccion`, sus índices, los tres triggers distintos, TLS 1.3 y los roles PostgreSQL separados.

![Verificación exitosa de RDS](img/pra-2/31-verificacion-rds-exitosa.jpg)

## 16. Retirar el acceso temporal

Al terminar la aplicación del esquema se eliminan la regla temporal de TCP 5432, el security group de CloudShell y el entorno temporal. RDS vuelve a quedar sin entradas hasta que se reciban los security groups definitivos de las EC2.

![RDS privado después de retirar el acceso temporal](img/pra-2/32-rds-sin-entradas-post-schema.jpg)

## Configuración comprobada

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
| Copias automatizadas | Habilitadas, retención de un día |
| Protección contra eliminación | Habilitada |
| Supervisión | Database Insights estándar; monitorización mejorada desactivada |

## Material complementario conservado

Las capturas numeradas `00`, `01`, `02` y `02b` se mantienen en `docs/img/pra-2/` como material complementario de auditoría. La secuencia de implementación documentada comienza en la captura `03`, que corresponde a la creación del security group.

## Trabajo pendiente para completar PRA-2

- Confirmar que la contraseña administrativa y las dos contraseñas de aplicación estén guardadas de forma privada.
- Recibir los security groups de las EC2 de Personas 2 y 3.
- Autorizar TCP 5432 únicamente desde esos dos security groups.
- Probar los usuarios separados de Node.js y Python desde sus EC2.
