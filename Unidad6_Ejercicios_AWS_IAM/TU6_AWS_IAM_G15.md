# Unidad 6 - Ejercicios AWS IAM

## Integrantes
- Rabbi
- Isai
- Javier
- Daniel

## Introducción
Breve explicación de AWS IAM.

---

# Ejercicio 6.1 - Crear un grupo IAM

**Responsables:** Rabbi e Isai

## Objetivo

## Procedimiento

### 1. Inicio de sesión como ROOT
[Captura]

### 2. Creación del grupo Administrators
[Captura]

### 3. Asignación de IAMFullAccess
[Captura]

## Resultado

## Referencia oficial de AWS

---

# Ejercicio 6.2 - Link personalizado y política de contraseñas

**Responsables:** Javier y Daniel

## Objetivo

Personalizar el enlace de inicio de sesión de la cuenta de AWS mediante un alias de cuenta, y configurar una política de contraseñas (password policy) personalizada para reforzar la seguridad de los usuarios de IAM, estableciendo requisitos mínimos de complejidad y un período de expiración.

## Procedimiento

### 1. Personalización del enlace de inicio de sesión

Desde el Panel de IAM, en la sección **Cuenta de AWS**, se seleccionó la opción **Crear** alias de cuenta. En el cuadro de diálogo se definió el alias `g15semi1`, con lo cual la URL de inicio de sesión para los usuarios de IAM cambió de la URL predeterminada (basada en el ID de cuenta `581117996165`) a la nueva URL personalizada `https://g15semi1.signin.aws.amazon.com/console`.

![AccountAlias1](/Unidad6_Ejercicios_AWS_IAM/Screenshots/6.1_AccountAlias.png)

Tras confirmar con el botón **Crear alias**, el sistema mostró el mensaje de confirmación *"Se creó el alias g15semi1 de esta cuenta"*, y el Panel de IAM quedó actualizado reflejando el nuevo alias y la nueva URL de acceso.

![AccountAlias2](/Unidad6_Ejercicios_AWS_IAM/Screenshots/6.1_AccountAliasCreated.png)

### 2. Configuración de la política de contraseñas

En **Configuración de cuenta > Política de contraseñas**, se seleccionó la opción **Editar** y se eligió **Personalizada** en lugar de los valores predeterminados de IAM. Se configuraron los siguientes requisitos:

- Longitud mínima de la contraseña: **12 caracteres**
- Exigir al menos un carácter en mayúscula (A-Z)
- Exigir al menos un carácter en minúscula (a-z)
- Exigir al menos un número
- Exigir al menos un carácter no alfanumérico
- Habilitar el vencimiento de contraseñas: expiración cada **90 días**

![PasswordPolicy](/Unidad6_Ejercicios_AWS_IAM/Screenshots/6.2_PasswordPolicy.png)

Al guardar los cambios, la consola confirmó la actualización con el mensaje *"Se han actualizado los requisitos de contraseña para los usuarios de IAM"*, y la sección de Configuración de cuenta mostró la nueva política de contraseñas personalizada aplicada correctamente.

![PasswordPolicy](/Unidad6_Ejercicios_AWS_IAM/Screenshots/6.2_PasswordPolicyCreated.png)

## Resultado

Se logró personalizar el acceso a la cuenta de AWS mediante el alias `g15semi1`, simplificando la URL de inicio de sesión para los usuarios de IAM. Adicionalmente, se estableció una política de contraseñas robusta (mínimo 12 caracteres, combinación de mayúsculas, minúsculas, números y símbolos, con expiración cada 90 días), lo que reduce el riesgo de accesos no autorizados y refuerza las buenas prácticas de seguridad en la gestión de credenciales de la cuenta.

## Referencia oficial de AWS

- AWS Identity and Access Management. *Configurar una política de contraseñas de IAM para usuarios de IAM*. Documentación de AWS IAM. https://docs.aws.amazon.com/es_es/IAM/latest/UserGuide/id_credentials_passwords_account-policy.html
- AWS Identity and Access Management. *Su ID de cuenta de AWS y su alias*. Documentación de AWS IAM. https://docs.aws.amazon.com/es_es/IAM/latest/UserGuide/console_account-alias.html

---

# Conclusiones

# Referencias