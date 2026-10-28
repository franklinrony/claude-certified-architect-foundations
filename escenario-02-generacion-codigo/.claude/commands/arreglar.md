---
description: Corrige un fallo ya localizado en una sola función
argument-hint: archivo, función, entrada y salida esperada
---

Corrige solo la función nombrada. No cambies otros archivos y no rediseñes el módulo.

Ejemplo de entrada: `precios.py`, `format_price`, la entrada `Decimal("19.90")` debe verse `"19.90"`.

Ejemplo de salida: el `return` deja el importe con dos decimales. El test de ese caso pasa. `pedidos.py` no se toca.
