---
description: Corrige un fallo ya localizado en una sola función
argument-hint: archivo, función, entrada y salida esperada
---

Corrige solo la función nombrada. No cambies otros archivos y no rediseñes el módulo.

No escribas en `start/`. Escribe la función corregida en la misma ruta bajo `end/catalogo/`. No edites `end/tests/`: esas pruebas ya dicen el resultado.

Ejemplo de entrada: `format_price`, la entrada `Decimal("19.90")` debe verse `"19.90"`.

Ejemplo de salida: `end/catalogo/precios.py` deja el importe con dos decimales. `start/catalogo/precios.py` sigue igual. `pedidos.py` no se toca.
