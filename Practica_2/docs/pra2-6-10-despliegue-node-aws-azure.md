# Despliegue de Node.js en AWS y Azure y Carga Serverless AWS — PRA2-6, PRA2-9 y PRA2-10

Registro de lo desplegado por Daniel. Contiene los nombres, identificadores, configuraciones de red, seguridad y estados del backend Node.js y la solución serverless en AWS. Las contraseñas, el `JWT_SECRET` y las llaves SSH se comparten **solo por mensaje privado** ([coordinación §3](coordinacion-equipo.md)).

Documentos relacionados: [coordinación del equipo](coordinacion-equipo.md) · [contrato serverless](contrato-serverless.md) · [paridad de backends](paridad-backends.md) · [README general](../README.md).

| Recurso | Grupo de recursos / Cuenta | Región | Identificador / URL |
|---|---|---|---|
| EC2 `taskflow-g15-node` | AWS (Cuenta compartida) | `us-east-1` | `i-0c9189f79dbfccc3e` |
| VM `taskflow-g15-node-azure` | Azure (`rg-taskflow-g15`) | West US 2 | IP Pública: `20.59.57.131` |
| API Gateway `taskflow-g15-serverless-api` | AWS (Cuenta compartida) | `us-east-1` | ID: `oaxm8gpqm0` · `https://oaxm8gpqm0.execute-api.us-east-1.amazonaws.com` |
| Lambdas Carga S3 | AWS (Cuenta compartida) | `us-east-1` | `lambda-image-upload`, `lambda-text-upload`, `lambda-file-upload` |

---

## 1. EC2 de AWS con el Backend Node.js (PRA2-10)

| Elemento | Valor |
|---|---|
| Nombre de Instancia | `taskflow-g15-node` |
| ID de Instancia | `i-0c9189f79dbfccc3e` |
| Región / AZ | `us-east-1` / `us-east-1a` |
| Imagen / Entorno | Ubuntu Server 24.04 LTS · Node.js 20.x · NestJS |
| Tamaño de Instancia | `t3.micro` |
| VPC / Subred | `vpc-07d71aba0ec5b2213` (VPC predeterminada) |
| Security Group | `taskflow-g15-node-sg` (`sg-0bbf5e7008267ff85`) |
| Reglas de Entrada SG | SSH `22` (TCP) y HTTP Node.js `3000` (TCP desde `sg-054b4346318f3c030`, Security Group del ALB) |
| Reglas de Salida SG | TCP `5432` directo hacia `rds-taskflow-g15` (`sg-063f677d0d31377a4`) |
| Gestor de Procesos | PM2 (`taskflow-node`) ejecutándose de forma persistente |

### 1.1 Instalación y Despliegue en EC2
- **Script de automatización:** [`aws/scripts/deploy-ec2-node.sh`](../aws/scripts/deploy-ec2-node.sh)
- **Gestión de variables:** `.env` cargado en la raíz de `api-node/` con credenciales de RDS PostgreSQL.
- **Compilación:** `npm run build` genera la salida optimizada en `dist/main.js`.
- **Persistencia:** `pm2 start dist/main.js --name "taskflow-node" --update-env` con inicio automático en systemd.

---

## 2. VM de Azure con el Backend Node.js (PRA2-10 Complemento)

| Elemento | Valor |
|---|---|
| Nombre de VM | `taskflow-g15-node-azure` |
| Grupo de Recursos | `rg-taskflow-g15` |
| Región | West US 2 |
| Imagen | Ubuntu Server 24.04 LTS · Node.js 20.x |
| Tamaño | `Standard_D2als_v7` (recompartido con Python) |
| Red Virtual / Subred | `vnet-westus2-1` / `snet-westus2-1` (misma VNet que Python para Load Balancer PRA2-19) |
| IP Pública | `20.59.57.131` (Estática) |
| IP Privada | `172.16.0.4` |
| NSG (Network Security Group) | Reglas de entrada: SSH `22` (TCP) y Node.js `3000` (TCP desde `0.0.0.0/0`) |
| Gestor de Procesos | PM2 (`taskflow-node`) ejecutándose como servicio persistente |

### 2.1 Conexión al RDS Privado desde Azure
- **Regla de Entrada en RDS Security Group:** Autorizado acceso PostgreSQL TCP `5432` desde la IP pública de la VM de Azure.
- **SSL / TLS:** Habilitado para comunicación cifrada con la base de datos PostgreSQL en Amazon RDS.

---

## 3. AWS Serverless: API Gateway + Lambdas + S3 (PRA2-9)

### 3.1 API Gateway HTTP (`taskflow-g15-serverless-api`)
- **Nombre:** `taskflow-g15-serverless-api`
- **ID de la API:** `oaxm8gpqm0`
- **Tipo:** HTTP API (API Gateway v2)
- **Dirección Base:** `https://oaxm8gpqm0.execute-api.us-east-1.amazonaws.com`
- **Etapa (Stage):** `$default` con despliegue automático (*Auto-deploy*).
- **Integración:** AWS Lambda Proxy Integration (Payload v2.0).

### 3.2 Matriz de Rutas y Lambdas

| Método HTTP | Ruta de API Gateway | Función Lambda Handler | Requisito Autenticación | Destino en S3 |
|---|---|---|---|---|
| `POST` | `/upload/image` | [`aws/serverless/lambda-image-upload.js`](../aws/serverless/lambda-image-upload.js) | **Pública** (Sin Token) | `profiles/pendientes/{uuid}-{nombre}` |
| `POST` | `/upload/text` | [`aws/serverless/lambda-text-upload.js`](../aws/serverless/lambda-text-upload.js) | **Protegida** (`Authorization: Bearer <TOKEN>`) | `files/{userId}/{uuid}-{nombre}` |
| `POST` | `/upload/file` | [`aws/serverless/lambda-file-upload.js`](../aws/serverless/lambda-file-upload.js) | **Protegida** (`Authorization: Bearer <TOKEN>`) | `files/{userId}/{uuid}-{nombre}` |

#### 3.2.1 Validación JWT y Estructura Multi-usuario
- **Verificación en Handlers:** Las funciones Lambda implementan verificación nativa del token JWT mediante el algoritmo HMAC-SHA256 (`HS256`) comparado contra `JWT_SECRET`.
- **Extracción Dinámica del `userId`:** Leen el claim `sub` del payload del JWT verificado para determinar dinámicamente el `userId` del usuario en sesión.
- **Formato de Clave Dinámica en S3:** Los archivos de CloudDrive se guardan dinámicamente en `files/{userId}/{uuid}-{nombreSeguro}` (eliminando cualquier ID estático `files/1/`).
- **Excepción de Foto de Perfil:** En `POST /upload/image`, si `destino: "perfil"`, la validación de token se omite por contrato y el objeto se guarda en `profiles/pendientes/{uuid}-{nombreSeguro}`.

---
- **Rol IAM de Ejecución:** `taskflow-lambda-s3-role`
- **Política IAM Asignada:** [`aws/iam/pra2-9-lambda-execution-policy.json`](../aws/iam/pra2-9-lambda-execution-policy.json)
- **Permisos Otorgados:** `s3:PutObject`, `s3:GetObject`, `s3:PutObjectAcl` sobre el bucket `arn:aws:s3:::practica2semi1a1s2026archivosg15/*` y logueo en Amazon CloudWatch Logs.

### 3.4 Configuración CORS
Configurado a nivel de API Gateway y en los encabezados devueltos por los handlers Lambda:
- **Allowed Origins:** `*` (provisional durante integración).
- **Allowed Methods:** `POST`, `OPTIONS`.
- **Allowed Headers:** `Content-Type`, `Authorization`.
- **Max Age Preflight:** `300` segundos.

---

## 4. Verificación de Funcionamiento (5 de octubre de 2026)

| Prueba / Endpoint | Entorno / Destino | Resultado Observado |
|---|---|---|
| `GET /health` | AWS EC2 (IP actual observada: `3.80.88.4:3000`) | La regla `3000` acepta solo el SG del ALB; la prueba debe ejecutarse mediante el DNS de PRA2-19 |
| `GET /health` | Azure VM (`20.59.57.131:3000`) | HTTP `200 OK`, `servicio: "taskflow-api"`, `implementacion: "node"` |
| `POST /upload/image` | API Gateway (`/upload/image`) | HTTP `201 Created`; Retorna `urlObjeto` HTTPS de S3 en `profiles/pendientes/` |
| `POST /upload/text` | API Gateway (`/upload/text`) | HTTP `201 Created`; Retorna `urlObjeto` HTTPS de S3 en `files/1/` |
| `POST /upload/file` | API Gateway (`/upload/file`) | HTTP `201 Created`; Retorna `urlObjeto` HTTPS de S3 en `files/1/` |
| `PATCH /api/v1/tasks/:taskId` | Backend Node.js (EC2/Azure) | HTTP `200 OK`; Cumple con línea 137 del estándar OpenAPI |

---

## 5. Artefactos Versionados

- **AWS IAM Policies:** [`aws/iam/pra2-10-ec2-node-policy.json`](../aws/iam/pra2-10-ec2-node-policy.json), [`aws/iam/pra2-9-lambda-execution-policy.json`](../aws/iam/pra2-9-lambda-execution-policy.json)
- **AWS Serverless Handlers:** [`aws/serverless/lambda-image-upload.js`](../aws/serverless/lambda-image-upload.js), [`aws/serverless/lambda-text-upload.js`](../aws/serverless/lambda-text-upload.js), [`aws/serverless/lambda-file-upload.js`](../aws/serverless/lambda-file-upload.js), [`aws/serverless/api-gateway-routes.json`](../aws/serverless/api-gateway-routes.json)
- **Deployment Scripts:** [`aws/scripts/deploy-ec2-node.sh`](../aws/scripts/deploy-ec2-node.sh), [`azure/vm/deploy-azure-vm-node.sh`](../azure/vm/deploy-azure-vm-node.sh)
