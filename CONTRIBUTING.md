# Contribuir a CloudCinema

## Flujo de ramas

- `main` contiene entregas estables.
- `develop` integra el trabajo aprobado del equipo.
- Cada cambio se desarrolla en una rama corta creada desde `develop`.

Use nombres descriptivos con el usuario de GitHub y la incidencia:

```text
usuario/pra-16-navegacion-frontend
```

## Commits

Los commits deben expresar una sola intención. Se recomienda Conventional
Commits:

```text
feat(frontend): agrega navegación inicial
fix(api-node): corrige código de error de autenticación
docs(data-model): actualiza restricciones relacionales
```

## Pull requests

1. Actualizar la rama desde `develop`.
2. Ejecutar lint, pruebas y build del componente afectado.
3. Revisar que no se incluyan secretos ni archivos `.env`.
4. Actualizar el contrato o documentación cuando cambie comportamiento público.
5. Abrir el pull request hacia `develop` y relacionarlo con la incidencia.
6. Resolver observaciones antes de integrar.

## Documentación

- El README contiene orientación y puesta en marcha, no seguimiento de tickets.
- Linear es la fuente de estado y asignación del trabajo.
- `Practica_1/contracts/openapi.yaml` es la fuente de verdad del contrato HTTP.
- `Practica_1/database/schema.sql` es la fuente ejecutable del modelo relacional.
- Las decisiones operativas y de infraestructura se mantienen resumidas en
  `README.md`; los detalles técnicos se actualizan en el documento específico
  correspondiente.
- El modelo relacional se mantiene en `Practica_1/docs/data-model/model.md` y la
  infraestructura en `Practica_1/docs/infrastructure.md`.
- Las instrucciones operativas describen el estado vigente; las evidencias
  históricas se conservan en `Practica_1/docs/evidence/`.
- Los archivos nuevos usan nombres en minúsculas y `kebab-case`, excepto los
  archivos convencionales reconocidos por GitHub.

## Verificación mínima

### Frontend

```bash
cd Practica_1/frontend
pnpm lint
pnpm build
```

### API Node.js

```bash
cd Practica_1/api-node
npm run build
npm test
```

Si una comprobación no puede ejecutarse, indíquelo claramente en el pull
request junto con la razón.
