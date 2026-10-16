# Infraestructura: API Gateway + Lambda de Carga de Imágenes (PRO-11)

Este directorio documenta la configuración reproducible de **Amazon API Gateway** integrado con la función **AWS Lambda** (`semisocial-g15-image-upload`) para el procesamiento y almacenamiento seguro de imágenes en Amazon S3.

---

## 1. Parámetros del Despliegue en AWS

* **Región:** `us-east-1`
* **Nombre de la Lambda:** `semisocial-g15-image-upload`
* **Runtime:** Node.js 22.x
* **Rol de Ejecución IAM:** `arn:aws:iam::581117996165:role/semisocial-g15-upload-lambda-role`
* **Tipo de API:** HTTP API (API Gateway v2)
* **Nombre de la API:** `semisocial-g15-upload-api`
* **API ID:** `xsjlh2s0d1`
* **Invoke URL Base:** `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com`
* **Endpoint de Carga:** `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images`
* **Ruta de Entrada:** `POST /uploads/images`
* **Integración:** AWS Lambda Proxy (`aws_proxy`, payload v2.0)
* **Etapa (Stage):** `$default` (Auto-deploy activado)
* **Bucket S3 Destino:** `semisocial-g15-images-581117996165`

---

## 2. Variables de Entorno de la Lambda

```env
AWS_REGION=us-east-1
S3_IMAGES_BUCKET=semisocial-g15-images-581117996165
S3_PROFILE_PREFIX=Fotos_Perfil/public/
S3_FACE_REFERENCE_PREFIX=Fotos_Perfil/references/
S3_FACE_CAPTURE_PREFIX=Fotos_Perfil/captures/
S3_POSTS_PREFIX=Fotos_Publicadas/
```

---

## 3. Comandos Reproducibles (AWS CLI)

### A. Empaquetar la Lambda
Desde la raíz del repositorio:
```bash
cd Proyecto_1/lambdas/image-upload
zip -r ../image-upload.zip index.js config.js multipart.js package.json
```

### B. Crear o Actualizar la Función Lambda
```bash
aws lambda create-function \
  --function-name semisocial-g15-image-upload \
  --runtime nodejs20.x \
  --role arn:aws:iam::581117996165:role/semisocial-g15-upload-lambda-role \
  --handler index.handler \
  --zip-file fileb://../image-upload.zip \
  --timeout 15 \
  --memory-size 256 \
  --region us-east-1 \
  --environment "Variables={S3_IMAGES_BUCKET=semisocial-g15-images-581117996165,S3_PROFILE_PREFIX=Fotos_Perfil/public/,S3_FACE_REFERENCE_PREFIX=Fotos_Perfil/references/,S3_FACE_CAPTURE_PREFIX=Fotos_Perfil/captures/,S3_POSTS_PREFIX=Fotos_Publicadas/}"
```

### C. Importar la Definición OpenAPI en API Gateway
```bash
aws apigatewayv2 create-api \
  --name "semisocial-g15-upload-api" \
  --protocol-type HTTP \
  --body file://openapi-api-gateway.yaml \
  --region us-east-1
```
