#!/usr/bin/env bash
set -euo pipefail

region_aws="${REGION_AWS:-us-east-1}"
bucket_imagenes="${BUCKET_IMAGENES:-practica1-images-g15}"
directorio_posteres="${1:-Practica_1/assets/posteres}"

posteres=(
  "el-gran-conejo.svg"
  "sintel.svg"
  "primavera.svg"
  "terror-de-duendes.svg"
  "el-sueno-de-los-elefantes.svg"
  "lagrimas-de-acero.svg"
  "lavanderia-cosmica.svg"
  "agente-327.svg"
  "carrera-por-cafe.svg"
  "carga.svg"
)

for poster in "${posteres[@]}"; do
  origen="${directorio_posteres}/${poster}"
  destino="s3://${bucket_imagenes}/Fotos_Peliculas/${poster}"

  if [[ ! -f "${origen}" ]]; then
    printf 'No se encontró el archivo requerido: %s\n' "${origen}" >&2
    exit 1
  fi

  aws s3 cp "${origen}" "${destino}" \
    --region "${region_aws}" \
    --content-type "image/svg+xml" \
    --cache-control "public,max-age=3600"
done

printf 'Pósteres cargados en s3://%s/Fotos_Peliculas/\n' "${bucket_imagenes}"
