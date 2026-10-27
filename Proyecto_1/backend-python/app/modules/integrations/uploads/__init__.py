"""Cargas de imágenes. El backend NO recibe archivos.

``POST /uploads/images`` vive en API Gateway + Lambda (PRO-11), que escribe en
S3 y devuelve ``{imageKey, imageUrl}``. Los backends solo reciben la clave y
deben comprobar que pertenece al ``cognito_sub`` autenticado y al prefijo
correcto (lo implementan PRO-14 para perfil y PRO-34 para posts).
"""

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = ("image/jpeg", "image/png", "image/webp")
