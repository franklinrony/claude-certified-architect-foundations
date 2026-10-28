# Catálogo de práctica

Estas reglas las carga Claude Code al abrir el proyecto. La Messages API no las lee solas.

- Los importes se calculan con `Decimal`. No uses `float`.
- `start/` es el ejemplo original. No edites nada dentro de `start/`.
- Todo el código modificado se escribe en `end/catalogo/`, conservando la misma ruta. Hay cinco fallos: `format_price`, `discounted_price`, `label_day`, `window_is_open` y `describe`.
- `end/tests/` es el contrato. No edites esas pruebas para ponerlas verdes.
- Un fallo localizado en una función se corrige en esa función, dentro de `end/`. No recorras el resto del catálogo.
- Para buscar en el código, empieza por el síntoma. No leas todos los archivos de entrada.

Las convenciones de pruebas no van aquí. Están en `.claude/rules/pruebas.md` y solo entran cuando se edita un test. Así el contexto no paga reglas que no aplican.
