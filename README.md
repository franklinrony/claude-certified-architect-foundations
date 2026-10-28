# Claude Certified Architect – Foundations (CCAR-F)

Práctica para el examen **Claude Certified Architect – Foundations** (CCAR-F, Exam Guide v1.0).

Este repositorio reúne la fuente del examen y un escenario por carpeta. Cada escenario es un ejercicio de estudio. No son preguntas oficiales.

La fuente de verdad está en [`docs/`](docs/):

- Exam Guide v1.0
- Hoja de ruta en español

Si otra fuente contradice esos documentos, gana el Exam Guide. Los términos del examen se dejan en inglés (`stop_reason`, `tool_use`, `end_turn`, MCP, hooks).

## Escenarios

Hay dos escenarios con carpeta. En PostgreSQL, base `ccar_f`, el esquema `escenario_02` sigue vacío: ese caso no guarda datos. Los esquemas `escenario_03` a `escenario_06` están reservados y todavía no tienen código.

| Escenario | Enlace | De qué trata |
| --- | --- | --- |
| 1. Customer Support Resolution Agent | [escenario-01-agente-soporte](escenario-01-agente-soporte/README.md) | Agente de soporte. Resuelve devoluciones, disputas de cobro y problemas de cuenta, y escala a una persona cuando la política lo pide. Usa el Claude Agent SDK y cuatro tools MCP: `get_customer`, `lookup_order`, `process_refund` y `escalate_to_human`. |
| 2. Code Generation with Claude Code | [escenario-02-generacion-codigo](escenario-02-generacion-codigo/README.md) | Claude Code para generar, corregir y documentar código. `CLAUDE.md`, un slash command, reglas con `paths`, y cuándo usar plan mode. No usa la Messages API. |

## Cómo está armado

- Un escenario por carpeta. El escenario 1 vive en `escenario-01-agente-soporte/`. El escenario 2 vive en `escenario-02-generacion-codigo/`.
- Los datos de práctica viven en PostgreSQL, base `ccar_f`, un esquema por escenario.
- La cadena de conexión y `ANTHROPIC_API_KEY` van en el `.env` de cada escenario. Ese archivo no se commitea. La plantilla del escenario 1 es [`.env.example`](escenario-01-agente-soporte/.env.example).
- Una regla de identidad, dinero o permisos se aplica en código o en un hook. Un prompt no basta.
- Los tests del escenario corren en local, sin llamar a la API.

El detalle de la base de datos, los tests y la corrida con Claude está en el [README del escenario 1](escenario-01-agente-soporte/README.md).
