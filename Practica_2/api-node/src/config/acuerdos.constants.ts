/**
 * Supuestos de trabajo acordados para la paridad Node.js / Python (PRA2-11).
 * 
 * Catálogo de errores, parámetros de bcrypt, JWT, formato de fechas e identificación.
 */

export const SERVICIO = 'taskflow-api';
export const IMPLEMENTACION = 'node';

export const SALUD_TIMEOUT_SEGUNDOS = 2.0;

// Contraseñas
export const BCRYPT_COSTO = 10;
export const BCRYPT_MAX_BYTES = 72;

// JWT
export const JWT_ALGORITMO = 'HS256';
export const TIPO_TOKEN = 'Bearer';
export const JWT_EXPIRACION_POR_DEFECTO = 3600;

// Patrones de validación
export const PATRON_NOMBRE_USUARIO = /^[a-z0-9_]+$/;
export const PATRON_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const PATRON_URL_HTTPS = /^https:\/\/\S+$/;

// Codigos de error
export const CODIGOS_ERROR = {
  ERROR_VALIDACION: 'ERROR_VALIDACION',
  ERROR_AUTENTICACION: 'ERROR_AUTENTICACION',
  NO_ENCONTRADO: 'NO_ENCONTRADO',
  CONFLICTO: 'CONFLICTO',
  ERROR_INTERNO: 'ERROR_INTERNO',
  BD_NO_DISPONIBLE: 'BD_NO_DISPONIBLE',
} as const;

export const MENSAJES_ERROR = {
  ERROR_VALIDACION: 'Los datos enviados no son válidos.',
  ERROR_AUTENTICACION: 'Token de autenticación ausente, inválido o expirado.',
  CREDENCIALES_INVALIDAS: 'Nombre de usuario o contraseña incorrectos.',
  NO_ENCONTRADO: 'El recurso solicitado no existe.',
  CONFLICTO_USUARIO: 'El nombre de usuario o el correo electrónico ya están registrados.',
  ERROR_INTERNO: 'Ocurrió un error inesperado en el servidor.',
  BD_NO_DISPONIBLE: 'La base de datos no está disponible.',
} as const;

export const DETALLES_ERROR = {
  NOMBRE_USUARIO_EXISTE: 'El nombre de usuario ya está registrado.',
  CORREO_EXISTE: 'El correo electrónico ya está registrado.',
  CONTRASENAS_NO_COINCIDEN: 'La confirmación no coincide con la contraseña.',
  ID_NO_ENTERO: 'Debe ser un número entero.',
} as const;
