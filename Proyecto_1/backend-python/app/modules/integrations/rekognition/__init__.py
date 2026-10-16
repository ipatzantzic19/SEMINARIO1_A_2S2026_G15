"""Adaptador de Rekognition DetectLabels. Pendiente: PRO-34.

Parámetros acordados en docs/api/labels.md. No expone rutas HTTP: lo invoca
el módulo de publicaciones al crear un post. Credenciales: instance profile
``semisocial-g15-backend-role`` (nunca access keys).
"""

MAX_LABELS = 20
MIN_CONFIDENCE = 80.0
ALLOWED_PREFIX = "Fotos_Publicadas/"
