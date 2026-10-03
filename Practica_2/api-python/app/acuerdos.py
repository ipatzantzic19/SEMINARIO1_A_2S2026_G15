"""Supuestos de trabajo acordados para la paridad Node.js / Python (PRA2-11).

Este es el ÚNICO lugar donde viven las decisiones que deben coincidir con el
backend Node.js: catálogo de errores y sus mensajes, parámetros de bcrypt y
JWT, formato de fechas, identificación del servicio y tiempos de /health.
Si el equipo cambia un acuerdo, se modifica aquí y el resto del código lo
toma automáticamente.
"""

from dataclasses import dataclass

# --- Identificación del servicio (RespuestaSalud) ---------------------------
SERVICIO = "taskflow-api"
IMPLEMENTACION = "python"

# --- /health -----------------------------------------------------------------
# Tiempo máximo para obtener una conexión y ejecutar SELECT 1.
SALUD_TIMEOUT_SEGUNDOS = 2.0

# --- Contraseñas ---------------------------------------------------------------
BCRYPT_COSTO = 10
# bcrypt solo usa los primeros 72 bytes. Node (bcrypt/bcryptjs) trunca en
# silencio; aquí se trunca igual para que un hash generado por cualquiera de
# los dos backends se verifique en el otro.
BCRYPT_MAX_BYTES = 72

# --- JWT -------------------------------------------------------------------------
JWT_ALGORITMO = "HS256"
TIPO_TOKEN = "Bearer"
# La expiración (segundos) se lee de JWT_EXPIRES_IN; 3600 es el valor por defecto.
JWT_EXPIRACION_POR_DEFECTO = 3600

# --- Fechas ------------------------------------------------------------------------
# ISO 8601 en UTC con milisegundos y sufijo Z: 2026-10-02T12:00:00.000Z
FECHA_PRECISION = "milliseconds"


# --- Catálogo de errores -------------------------------------------------------------
@dataclass(frozen=True)
class CodigoError:
    codigo: str
    estado_http: int


ERROR_VALIDACION = CodigoError("ERROR_VALIDACION", 400)
ERROR_AUTENTICACION = CodigoError("ERROR_AUTENTICACION", 401)
NO_ENCONTRADO = CodigoError("NO_ENCONTRADO", 404)
CONFLICTO = CodigoError("CONFLICTO", 409)
ERROR_INTERNO = CodigoError("ERROR_INTERNO", 500)
BD_NO_DISPONIBLE = CodigoError("BD_NO_DISPONIBLE", 503)

# Mensajes principales (campo `error.mensaje`).
MENSAJE_VALIDACION = "Los datos enviados no son válidos."
MENSAJE_TOKEN_INVALIDO = "Token de autenticación ausente, inválido o expirado."
MENSAJE_CREDENCIALES_INVALIDAS = "Nombre de usuario o contraseña incorrectos."
MENSAJE_NO_ENCONTRADO = "El recurso solicitado no existe."
MENSAJE_CONFLICTO_USUARIO = "El nombre de usuario o el correo electrónico ya están registrados."
MENSAJE_ERROR_INTERNO = "Ocurrió un error inesperado en el servidor."
MENSAJE_BD_NO_DISPONIBLE = "La base de datos no está disponible."

# Mensajes de detalle (campo `error.detalles[].mensaje`).
DETALLE_NOMBRE_USUARIO_EXISTE = "El nombre de usuario ya está registrado."
DETALLE_CORREO_EXISTE = "El correo electrónico ya está registrado."
DETALLE_CONTRASENAS_NO_COINCIDEN = "La confirmación no coincide con la contraseña."
DETALLE_CUERPO_OBLIGATORIO = "El cuerpo de la solicitud es obligatorio."
DETALLE_JSON_INVALIDO = "El cuerpo de la solicitud no es un JSON válido."
DETALLE_TEXTO_EN_BLANCO = "No puede estar vacío ni contener solo espacios."

# Mensajes de 404 por recurso. Se usan tanto si el recurso no existe como si
# pertenece a otro usuario: nunca se revela que existe.
MENSAJE_TAREA_NO_ENCONTRADA = "La tarea no existe."
MENSAJE_ARCHIVO_NO_ENCONTRADO = "El archivo no existe."

# --- Identificadores de ruta (taskId, fileId) --------------------------------------
# Enteros >= 1 y dentro del rango BIGINT de PostgreSQL; fuera de eso, 400.
ID_MINIMO = 1
ID_MAXIMO = 9_223_372_036_854_775_807

# --- Tareas --------------------------------------------------------------------------
# Los listados van de la más reciente a la más antigua; a igual fecha, el id
# mayor primero, para que el orden sea determinista en ambos backends.
#   tareas:   ORDER BY fecha_creacion DESC, id DESC
#   archivos: ORDER BY creado_en DESC, id DESC
# fechaCreacion (opcional) debe incluir zona horaria (RFC 3339, p. ej. ...Z o
# -06:00); sin zona sería ambigua y Node la interpretaría con la hora local.
# PUT acepta fechaCreacion por contrato pero la ignora: solo cambia título y descripción.
# PATCH con el mismo valor de `completada` no modifica la fila (conserva
# fechaCompletada y actualizadoEn).

# --- Archivos ------------------------------------------------------------------------
# proveedorAlmacenamiento distingue mayúsculas: solo "S3" o "BLOB".
PROVEEDORES_ALMACENAMIENTO = ("S3", "BLOB")

# Traducción de los errores de validación de pydantic al español.
# Las llaves son el `type` de pydantic; los textos admiten los valores de `ctx`.
TRADUCCIONES_VALIDACION = {
    "missing": "El campo es obligatorio.",
    "extra_forbidden": "El campo no está permitido.",
    "string_type": "Debe ser una cadena de texto.",
    "string_too_short": "Debe tener al menos {min_length} caracteres.",
    "string_too_long": "Debe tener como máximo {max_length} caracteres.",
    "string_pattern_mismatch": "El formato no es válido.",
    "bool_type": "Debe ser un valor booleano.",
    "int_type": "Debe ser un número entero.",
    "int_parsing": "Debe ser un número entero.",
    "greater_than_equal": "Debe ser mayor o igual que {ge}.",
    "less_than_equal": "Debe ser menor o igual que {le}.",
    "timezone_aware": "La fecha debe incluir zona horaria (por ejemplo, Z).",
    "literal_error": "Debe ser uno de los valores permitidos: {expected}.",
    "enum": "Debe ser uno de los valores permitidos: {expected}.",
    "datetime_type": "Debe ser una fecha y hora en formato ISO 8601.",
    "datetime_parsing": "Debe ser una fecha y hora en formato ISO 8601.",
    "datetime_from_date_parsing": "Debe ser una fecha y hora en formato ISO 8601.",
    "model_attributes_type": "El cuerpo de la solicitud debe ser un objeto JSON.",
    "dict_type": "El cuerpo de la solicitud debe ser un objeto JSON.",
    "json_invalid": DETALLE_JSON_INVALIDO,
}
MENSAJE_VALIDACION_GENERICO = "El valor no es válido."

# Mensajes de formato específicos por campo (sustituyen a string_pattern_mismatch).
MENSAJES_FORMATO_POR_CAMPO = {
    "nombreUsuario": "Solo se permiten letras minúsculas, números y guion bajo.",
    "correoElectronico": "Debe ser un correo electrónico válido.",
    "urlImagenPerfil": "Debe ser una URL que comience con https://.",
    "urlObjeto": "Debe ser una URL que comience con https://.",
}

# Mensajes de valores permitidos por campo (sustituyen a literal_error).
MENSAJES_VALORES_PERMITIDOS_POR_CAMPO = {
    "proveedorAlmacenamiento": "Debe ser S3 o BLOB.",
}

# --- Unicidad de usuarios (nombres de índice en database/schema.sql) -------------
INDICES_UNICOS_USUARIO = {
    "uq_usuarios_nombre_usuario": ("nombreUsuario", DETALLE_NOMBRE_USUARIO_EXISTE),
    "uq_usuarios_correo_electronico": ("correoElectronico", DETALLE_CORREO_EXISTE),
}
