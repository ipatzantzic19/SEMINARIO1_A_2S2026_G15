# Revisión de criterios — PRA-4

## Criterios cubiertos

- [x] Se identificaron los accesos requeridos por los dos servicios.
- [x] Existen dos roles EC2 separados y dos perfiles de instancia.
- [x] No se concedieron permisos administrativos globales.
- [x] La política limita S3 al bucket y prefijos de CloudCinema.
- [x] Los backends pueden leer y subir objetos mediante SDK.
- [x] El borrado y otros buckets están denegados por omisión.
- [x] No se requieren claves AWS permanentes en archivos o variables del servidor.
- [x] Se preparó la entrega no secreta para Personas 2 y 3.
- [x] Se documentaron tabla de identidades, mapa de acceso y capturas.

## Validación realizada

La política versión 2 quedó predeterminada y asociada a ambos roles. El simulador IAM confirmó permisos positivos y negativos, y AWS CLI confirmó los dos perfiles de instancia.

## Pendiente para cierre integral

- [ ] Adjuntar `CloudCinema-Node-S3-PRA3` a la EC2 de PRA-10.
- [ ] Adjuntar `CloudCinema-Python-S3-PRA3` a la EC2 de PRA-15.
- [ ] Ejecutar una carga real desde cada SDK cuando los backends estén disponibles.

La configuración bajo responsabilidad de Persona 1 está completada. El ticket debe permanecer en progreso hasta registrar la integración final o acordar con el equipo que esta validación se hará en los tickets de despliegue.
