# fixtures/

Datos mínimos para pruebas automatizadas.

- Nunca se mezclan con `data/cases/`: un fixture no es un caso del sistema y el catálogo no lo carga.

## Casos

| Archivo | Origen | Para qué sirve |
| --- | --- | --- |
| `cases/MED-900.json` | Caso escrito a mano en la rama Rodrigo (`CARD-001`, 9493e8b). Se renombró a `MED-900` porque el prefijo debe corresponder a la especialidad (regla R01); el contenido no cambia. | Pruebas del sistema multiagente: tiene datos en `on_request` para los cinco roles (paciente, médico asistente, laboratorio, radiología y especialista). |
