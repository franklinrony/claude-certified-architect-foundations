# Regla de estudio CCAR-F

Este repositorio prepara Claude Certified Architect – Foundations (CCAR-F, Exam Guide v1.0).

## Fuente

- La fuente de verdad es `docs/`. Antes de cambiar código o explicar un escenario, usa el Exam Guide y la hoja de ruta en español que están ahí.
- Si un repositorio comunitario o una respuesta genérica contradice `docs/`, gana el Exam Guide.
- Conserva los términos oficiales en inglés: `stop_reason`, `tool_use`, `end_turn`, nombres de tools, MCP, hooks, `tool_choice`.
- La primera vez que una respuesta use un término de la Claude API, del Claude Agent SDK, de Claude Code o de MCP, explícalo en una o dos frases: qué es, quién lo produce (la API, el SDK o código de este repo) y en qué archivo de este proyecto se ve. No des por conocido el término. Si vuelve a salir en la misma respuesta, no repitas el glosario. Esta regla vale solo en este repositorio.

## Alcance

- Todo el trabajo es sobre Claude: Claude API, Claude Agent SDK, Claude Code y MCP.
- No propongas ni agregues otros proveedores de modelos.
- La llamada a Claude queda solo donde el ejercicio no se puede aprender sin el modelo. Contratos, tools, hooks, fixtures, errores y tests corren en local, sin API.
- No inventes preguntas de examen ni las presentes como oficiales. Los ejercicios de la hoja de ruta son práctica, no ítems reales.

## Cómo trabajar

- Un escenario por carpeta. El escenario 1 vive en `escenario-01-agente-soporte/`.
- Los datos de práctica están en PostgreSQL, base `ccar_f`, un esquema por escenario (`escenario_01` … `escenario_06`). La cadena de conexión vive en el `.env` del escenario. No la copies a otros archivos.
- No commitees `.env`, claves ni `ANTHROPIC_API_KEY`.
- Una regla de identidad, dinero o permisos se aplica en código o en un hook. Un prompt no basta.
- Antes de dar un cambio por terminado, corre los tests del escenario que tocaste.
