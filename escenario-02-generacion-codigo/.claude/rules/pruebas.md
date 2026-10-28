---
paths:
  - "**/test_*.py"
---

# Pruebas

Esta regla aplica a los tests estén en la carpeta que estén. Un `CLAUDE.md` por subcarpeta no alcanzaría: los tests no viven todos en el mismo directorio.

- El archivo se llama `test_*.py`.
- Cada prueba se llama `test_...`.
- Un test afirma un caso. No esconde otro archivo dentro del mismo assert.
