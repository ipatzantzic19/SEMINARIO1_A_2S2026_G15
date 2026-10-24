"""Adaptador de Rekognition DetectLabels (PRO-34).

Parámetros acordados en docs/api/labels.md. No expone rutas HTTP: lo invoca
el módulo de publicaciones al crear un post. Credenciales: instance profile
``semisocial-g15-backend-role`` (nunca access keys).

- ``client.py``: cliente boto3 (sesión propia, timeouts, sin reintentos propios).
- ``labels.py``: diccionario español y normalización de etiquetas.
- ``detector.py``: DetectLabels con reintentos 250/750 ms y errores de la tabla común.
"""

MAX_LABELS = 20
MIN_CONFIDENCE = 80.0
ALLOWED_PREFIX = "Fotos_Publicadas/"
