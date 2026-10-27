"""Catálogo de códigos y mensajes (contrato serverless §8).

Los códigos y los mensajes comunes son copia textual de
`api-python/app/acuerdos.py`: la Function se publica sola y no puede importar
el backend. Si cambia un acuerdo allí, se cambia también aquí.
No hay códigos nuevos.
"""

# --- Códigos y estado HTTP -----------------------------------------------------
ERROR_VALIDACION = ("ERROR_VALIDACION", 400)
ERROR_AUTENTICACION = ("ERROR_AUTENTICACION", 401)
NO_ENCONTRADO = ("NO_ENCONTRADO", 404)
ERROR_INTERNO = ("ERROR_INTERNO", 500)

# --- Mensajes principales (error.mensaje) ----------------------------------------
MENSAJE_VALIDACION = "Los datos enviados no son válidos."
MENSAJE_TOKEN_INVALIDO = "Token de autenticación ausente, inválido o expirado."
MENSAJE_NO_ENCONTRADO = "El recurso solicitado no existe."
MENSAJE_ERROR_INTERNO = "Ocurrió un error inesperado en el servidor."

# --- Detalles comunes con el backend ---------------------------------------------
DETALLE_OBLIGATORIO = "El campo es obligatorio."
DETALLE_NO_PERMITIDO = "El campo no está permitido."
DETALLE_TIPO_TEXTO = "Debe ser una cadena de texto."
DETALLE_MAXIMO_255 = "Debe tener como máximo 255 caracteres."
DETALLE_TEXTO_EN_BLANCO = "No puede estar vacío ni contener solo espacios."
DETALLE_CUERPO_OBLIGATORIO = "El cuerpo de la solicitud es obligatorio."
DETALLE_JSON_INVALIDO = "El cuerpo de la solicitud no es un JSON válido."
DETALLE_CUERPO_NO_OBJETO = "El cuerpo de la solicitud debe ser un objeto JSON."

# --- Detalles propios de la carga (contrato §8) -----------------------------------
DETALLE_TIPO_MIME_FORMATO = "Debe ser un tipo MIME en minúsculas y sin parámetros (por ejemplo, image/png)."
DETALLE_TIPO_NO_PERMITIDO = "Tipo de archivo no permitido en esta ruta."
DETALLE_EXTENSION_BLOQUEADA = "Extensión de archivo no permitida."
DETALLE_DESTINO_VALOR = "Debe ser archivo o perfil."
DETALLE_DESTINO_PERFIL = "Solo /upload/image admite el destino perfil."
DETALLE_BASE64_INVALIDO = "Debe ser base64 estándar válido."
DETALLE_CONTENIDO_VACIO = "El contenido no puede estar vacío."
DETALLE_TAMANO_EXCEDIDO = "El contenido supera el tamaño máximo de {mib} MiB."
DETALLE_NO_ES_IMAGEN = "El contenido no es una imagen JPEG, PNG, GIF o WebP."
DETALLE_NO_ES_UTF8 = "El contenido no es texto UTF-8 válido."
DETALLE_CONTENIDO_BLOQUEADO = "El contenido corresponde a un tipo de archivo no permitido."
