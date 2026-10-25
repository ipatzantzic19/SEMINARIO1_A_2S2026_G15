"""Normalización de etiquetas de Rekognition (docs/api/labels.md).

``SPANISH_LABEL_MAP`` es copia literal del diccionario de
``backend-node/src/modules/posts/rekognition.service.ts``; una prueba compara
ambos leyendo el archivo de Node, de modo que no pueden divergir sin avisar.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SPANISH_LABEL_MAP: dict[str, str] = {
    "dog": "perro",
    "canine": "canino",
    "pet": "mascota",
    "animal": "animal",
    "mammal": "mamífero",
    "cat": "gato",
    "feline": "felino",
    "outdoors": "exterior",
    "nature": "naturaleza",
    "building": "edificio",
    "architecture": "arquitectura",
    "campus": "campus",
    "university": "universidad",
    "school": "escuela",
    "person": "persona",
    "human": "humano",
    "people": "gente",
    "landscape": "paisaje",
    "tree": "árbol",
    "plant": "planta",
    "flower": "flor",
    "technology": "tecnología",
    "computer": "computadora",
    "electronics": "electrónica",
    "city": "ciudad",
    "urban": "urbano",
    "street": "calle",
    "car": "vehículo",
    "automobile": "automóvil",
    "sky": "cielo",
    "cloud": "nube",
    "water": "agua",
}

MAX_NAME_CHARS = 255  # post_labels.source_label es varchar(255)
_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class NormalizedLabel:
    name: str  # normalized_label: trim + NFC + minúsculas + diccionario español
    confidence: Decimal  # 2 decimales, ROUND_HALF_UP
    source_name: str  # nombre original de Rekognition (source_label)


def round_confidence(raw: Any) -> Decimal:
    """Redondea a 2 decimales con ROUND_HALF_UP sobre la representación decimal del valor."""
    return Decimal(str(raw)).quantize(_CENTS, rounding=ROUND_HALF_UP)


def normalize_label(source_name: str, raw_confidence: Any) -> NormalizedLabel:
    trimmed = unicodedata.normalize("NFC", (source_name or "").strip())
    lower = trimmed.lower()
    return NormalizedLabel(
        name=SPANISH_LABEL_MAP.get(lower, lower),
        confidence=round_confidence(raw_confidence),
        source_name=trimmed,
    )


def normalize_filter(value: str) -> str:
    """Mismo recorte que ``normalize_label`` para comparar un filtro del cliente."""
    return unicodedata.normalize("NFC", value.strip()).lower()
