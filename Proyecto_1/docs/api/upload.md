# Documentación Técnica: API de Carga de Imágenes (PRO-11)

**Ticket:** PRO-11 — Implementar carga de imágenes con API Gateway y Lambda  
**Fase:** 2 — Multimedia  
**Directorio:** `Proyecto_1/lambdas/image-upload/`  
**Infraestructura:** `Proyecto_1/infra/api-gateway/`  
**Estado:** Implementado, verificado y probado (9/9 pruebas unitarias pasando)

---

## 1. Arquitectura de Carga Multimedia

De acuerdo con el contrato común ([contract.md](contract.md)), las imágenes **nunca** pasan por los servidores EC2 ni se entregan URLs presignadas de PUT directo al navegador:



---

## 2. Contrato de Endpoint (`POST /uploads/images`)

* **URL:** `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com/uploads/images`  
* **URL Base de API Gateway:** `https://xsjlh2s0d1.execute-api.us-east-1.amazonaws.com`  
* **Método:** `POST`  
* **Content-Type:** `multipart/form-data`  

### Parámetros del Formulario

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `file` | Binario | **Sí** | Archivo de imagen real (JPEG, PNG o WebP). Máximo **5 MiB** (5,242,880 bytes). |
| `purpose` | String | **Sí** | Enum: `profile`, `post`, `faceCapture`. |
| `challengeId` | UUID | Condicional | **Obligatorio** si `purpose === 'faceCapture'`. |
| `sha256` | String | No | Hash SHA-256 en minúsculas (64 caracteres hex) para validación de integridad. |

### Reglas de Autenticación por Propósito

1. **`purpose=profile`**:
   * Requiere cabecera: `Authorization: Bearer <token_cognito>`.
   * **Permitido para perfiles incompletos** (`profileComplete=false`) para habilitar la carga de la foto obligatoria de registro.
2. **`purpose=post`**:
   * Requiere cabecera: `Authorization: Bearer <token_cognito>`.
3. **`purpose=faceCapture`**:
   * Requiere cabecera: `X-Face-Upload-Token: <token>` o `Authorization: Bearer <token>`.
   * Vinculado exclusivamente al `challengeId` del reto facial (PRO-31). Nunca es anónimo.

---

## 3. Comportamiento en S3 y Respuestas (`201 Created`)

### A. Foto de Perfil (`purpose=profile`)
La Lambda guarda la foto pública y **genera automáticamente la copia privada de referencia**:
* **Objeto Público:** `Fotos_Perfil/public/<cognitoSub>/<uuid>.<ext>`
* **Objeto Privado:** `Fotos_Perfil/references/<cognitoSub>/<uuid>.<ext>`
* **Respuesta JSON (`201 Created`):**
  ```json
  {
    "imageKey": "Fotos_Perfil/public/c09a8123-1122-3344-5566-778899aabbcc/1bf6f6c4-873e-486a-847e-aeaf52aa4e2e.jpg",
    "imageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Perfil/public/c09a8123-1122-3344-5566-778899aabbcc/1bf6f6c4-873e-486a-847e-aeaf52aa4e2e.jpg"
  }
  ```

### B. Foto de Publicación (`purpose=post`)
* **Objeto Público:** `Fotos_Publicadas/<cognitoSub>/<uuid>.<ext>`
* **Respuesta JSON (`201 Created`):**
  ```json
  {
    "imageKey": "Fotos_Publicadas/c09a8123-1122-3344-5566-778899aabbcc/3fa85f64-5717-4562-b3fc-2c963f66afa6.png",
    "imageUrl": "https://semisocial-g15-images-581117996165.s3.us-east-1.amazonaws.com/Fotos_Publicadas/c09a8123-1122-3344-5566-778899aabbcc/3fa85f64-5717-4562-b3fc-2c963f66afa6.png"
  }
  ```

### C. Captura Facial Efímera (`purpose=faceCapture`)
* **Objeto Privado:** `Fotos_Perfil/captures/<challengeId>/<uuid>.<ext>`
* **Respuesta JSON (`201 Created`):**
  ```json
  {
    "imageKey": "Fotos_Perfil/captures/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/4fa85f64-5717-4562-b3fc-2c963f66afa6.webp",
    "imageUrl": null
  }
  ```
  *(Nota: `imageUrl` es estrictamente `null` para impedir la exposición de datos biométricos).*

---

## 4. Respuestas de Error Estandarizadas

| Código HTTP | `code` | Causa |
|---|---|---|
| **400** | `VALIDATION_ERROR` | Falta `purpose`, valor inválido, falta `challengeId` en captura o sha256 no coincide. |
| **401** | `UNAUTHENTICATED` | Cabecera `Authorization` ausente o token inválido/malformado. |
| **413** | `FILE_TOO_LARGE` | El archivo supera los 5 MiB (5,242,880 bytes). |
| **415** | `UNSUPPORTED_MEDIA_TYPE` | El archivo no es una imagen real JPEG, PNG o WebP (verificado por Magic Bytes). |

---

## 5. Notas de Handoff

* **Para Guo (Frontend React):**
  * Configura `VITE_UPLOAD_BASE_URL` apuntando al endpoint de API Gateway.
  * Al enviar la foto de perfil en el registro:
    ```javascript
    const formData = new FormData();
    formData.append('purpose', 'profile');
    formData.append('file', fileBlob);
    
    const res = await fetch(`${UPLOAD_URL}/uploads/images`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${accessToken}` },
      body: formData,
    });
    const { imageKey, imageUrl } = await res.json();
    ```
  * Luego, envía ese `imageKey` al backend Node o Python llamando a `POST /api/v1/me/complete-profile` con `{ "profileImageKey": imageKey }` para activar el perfil.
* **Para Isai (S3 / Triggers Facial):**
  * La Lambda escribe en los prefijos acordados de `semisocial-g15-images-581117996165`.
  * La copia privada en `Fotos_Perfil/references/<cognitoSub>/` queda lista para que tu trigger `VerifyAuthChallengeResponse` (PRO-31) pueda compararla contra `Fotos_Perfil/captures/` usando Rekognition.
