#!/usr/bin/env bash
set -euo pipefail

region_aws="${REGION_AWS:-us-east-1}"
bucket_imagenes="${BUCKET_IMAGENES:-practica1-images-g15}"

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
  url="https://${bucket_imagenes}.s3.${region_aws}.amazonaws.com/Fotos_Peliculas/${poster}"
  codigo_http="$(curl --silent --output /dev/null --write-out '%{http_code}' "${url}")"

  if [[ "${codigo_http}" != "200" ]]; then
    printf 'FALLO %s -> HTTP %s\n' "${poster}" "${codigo_http}" >&2
    exit 1
  fi

  printf 'OK %s -> HTTP %s\n' "${poster}" "${codigo_http}"
done

printf 'VERIFICACION_PRA_5_POSTERES_COMPLETA\n'
