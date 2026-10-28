---
name: explorar
description: Rastrea un flujo del catálogo y devuelve un resumen corto
context: fork
allowed-tools: Read, Grep, Glob
argument-hint: qué flujo hay que seguir, por ejemplo quién llama a format_price
---

# Explorar

Busca solo el flujo pedido. Devuelve los archivos, las funciones y el dato exacto que encontraste.

No pegues el archivo completo en la respuesta. El modo `context: fork` corre esta skill en un subagente aislado para que esa lectura no llene la conversación principal.
