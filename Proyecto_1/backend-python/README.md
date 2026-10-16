# Semi-Social — Backend Python (FastAPI)

Implementación Python del contrato común (`../docs/api/openapi.yaml`), segundo
target del ALB junto a `backend-node`. Documentación completa, estado de
módulos y diferencias con Node: [`../docs/api/python.md`](../docs/api/python.md).

## Inicio rápido (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env   # APP_ENV=local
python -m app                 # http://127.0.0.1:3000/health
python -m pytest
```

- Puerto `3000`; `GET /health` en la raíz; negocio bajo `/api/v1`.
- Si `APP_ENV` no está definida se asume `production` y se exigen Cognito,
  RDS y S3 reales.
- Swagger en `http://127.0.0.1:3000/api/docs` solo con `APP_ENV=local`.
- Token local de prueba: `python scripts\local_token.py` y
  `AUTH_LOCAL_PUBLIC_KEY_FILE=.local/jwt-public.pem` en `.env`.

No versionar `.env`, `.local/` ni llaves.
