# GitFlow del equipo

## Objetivo

Este flujo permite desarrollar varias partes de CloudCinema en paralelo sin trabajar directamente sobre la versión estable. Linear indica **qué** se debe hacer y Git registra **cómo** cambió el proyecto.

## Ramas

| Rama | Propósito | Quién integra cambios |
|---|---|---|
| `main` | Versión estable y entregable | El equipo mediante una rama `release/*` |
| `develop` | Integración de funcionalidades terminadas | Pull requests aprobados |
| `<usuario>/<ticket>-<descripcion>` | Trabajo de una incidencia de Linear | Su responsable |
| `release/<nombre>` | Preparación y correcciones de una entrega | El equipo |
| `hotfix/<descripcion>` | Corrección urgente de algo ya publicado en `main` | El equipo |

La rama de PRA-1 es:

```text
ipatzantzic/pra-1-disenar-contrato-api-y-modelo-relacional
```

## Flujo normal de una incidencia

```text
main
  └── develop
        └── usuario/ticket-descripcion
              └── Pull Request hacia develop
```

1. Confirmar en Linear que la incidencia está lista para iniciar.
2. Actualizar `develop` local.
3. Crear la rama de trabajo desde `develop`.
4. Cambiar la incidencia a `In Progress` cuando el trabajo realmente comience.
5. Hacer commits pequeños y comprensibles.
6. Subir la rama y abrir un pull request hacia `develop`.
7. Revisar los criterios de aceptación y solicitar revisión a un compañero.
8. Integrar el pull request cuando esté aprobado y verificado.
9. Cambiar la incidencia a `Done` únicamente cuando todos los criterios, documentación y evidencias estén completos.

## Comandos para comenzar una incidencia

```bash
git switch develop
git pull origin develop
git switch -c usuario/ticket-descripcion
```

Ejemplo:

```bash
git switch develop
git pull origin develop
git switch -c ipatzantzic/pra-2-crear-y-configurar-amazon-rds
```

## Commits

Formato recomendado:

```text
tipo(PRA-N): descripción breve en imperativo
```

Tipos útiles:

- `feat`: funcionalidad nueva.
- `docs`: documentación.
- `fix`: corrección.
- `test`: pruebas.
- `chore`: configuración o mantenimiento.
- `refactor`: reorganización sin cambiar el comportamiento.

Ejemplos:

```text
docs(PRA-1): documentar contrato común de endpoints
feat(PRA-2): agregar esquema inicial de PostgreSQL
chore(PRA-3): preparar configuración del bucket de imágenes
```

No colocar secretos, contraseñas ni tokens en commits, archivos, descripciones de pull requests o comentarios de Linear.

## Pull requests

Una rama de incidencia siempre propone cambios hacia `develop`, nunca directamente hacia `main`.

Antes de aprobar un pull request se debe comprobar:

- La incidencia de Linear está enlazada o mencionada.
- Se cumplieron todos sus criterios de aceptación.
- No hay secretos ni credenciales versionadas.
- La documentación y evidencias necesarias están incluidas.
- El cambio no rompe el trabajo ya integrado.
- Al menos un compañero revisó el cambio cuando sea posible.

## Preparar una entrega

Cuando `develop` contenga todas las incidencias de la entrega:

```bash
git switch develop
git pull origin develop
git switch -c release/practica-1-v1.0.0
```

En `release/*` solo se permiten pruebas finales, documentación y correcciones de entrega. Cuando esté lista, se integra a `main` y también de vuelta a `develop`; luego se etiqueta la versión:

```bash
git switch main
git tag -a practica-1-v1.0.0 -m "Entrega Práctica 1"
git push origin practica-1-v1.0.0
```

## Correcciones urgentes

Un `hotfix/*` nace desde `main`. Después de corregir, se integra tanto en `main` como en `develop` para que la solución no se pierda en trabajos futuros.

## Relación entre Git y Linear

Linear mantiene el estado, responsable, dependencias y criterios. GitHub contiene los archivos, commits, revisiones y versiones. Un ticket no pasa a `Done` solo porque su rama exista: primero debe integrarse y cumplir completamente su definición de terminado.

