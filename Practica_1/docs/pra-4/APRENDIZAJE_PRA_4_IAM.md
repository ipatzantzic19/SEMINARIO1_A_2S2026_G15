# Aprendizaje — PRA-4 IAM

## Conceptos clave

- Un usuario IAM representa normalmente a una persona o integración que requiere credenciales; un rol puede ser asumido temporalmente por un servicio como EC2.
- Una política define acciones, recursos y condiciones; adjuntarla a un rol no obliga a usar llaves permanentes.
- Mínimo privilegio significa justificar cada acción. Si el caso de uso solo lee y sube imágenes, `DeleteObject` es innecesario.
- Separar el rol de Node.js del rol de Python permite auditar, revocar o modificar un backend sin afectar la identidad del otro.
- Una denegación implícita ocurre cuando ninguna política concede la acción. Es suficiente para bloquear borrado y acceso a otros buckets.

## Cómo explicarlo al equipo

La EC2 recibe un perfil de instancia. El SDK solicita credenciales temporales mediante el entorno de AWS y firma las peticiones automáticamente. El repositorio conserva nombres de recursos y políticas, pero nunca claves de acceso.

Ambos backends necesitan las mismas operaciones de S3, por eso comparten una política. Mantienen roles distintos porque son dos cargas de trabajo independientes.

## Error evitado

Conservar `s3:DeleteObject` habría permitido borrar fotos o pósteres por error. También era excesivo permitir `ListBucket` sin condición, porque el backend solo debe conocer los dos prefijos del proyecto.

## Verificación personal

- [ ] Puedo explicar la diferencia entre usuario, rol, política y perfil de instancia.
- [ ] Puedo identificar acción, recurso y condición en el JSON.
- [ ] Puedo justificar por qué no se crearon usuarios IAM para los backends.
- [ ] Puedo demostrar qué acciones se permiten y cuáles se deniegan.
- [ ] Puedo explicar cómo Persona 2 y Persona 3 adjuntarán sus roles.
