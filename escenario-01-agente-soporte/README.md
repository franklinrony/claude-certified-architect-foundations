# Escenario 1 — Customer Support Resolution Agent

Práctica del escenario 1 del Exam Guide v1.0 (CCAR-F). Un agente de soporte resuelve devoluciones, disputas de cobro y problemas de cuenta, y sabe cuándo escalar.

La fuente de este ejercicio es `docs/` en la raíz del repo. Los términos del examen se dejan en inglés. Lo que este caso enseña, y en qué orden abrirlo, está en [APRENDIZAJE.md](APRENDIZAJE.md).

## En qué consiste

El Exam Guide describe un agente de soporte hecho con el Claude Agent SDK. Atiende pedidos ambiguos: returns, billing disputes y account issues. El backend se consulta solo con cuatro tools MCP: `get_customer`, `lookup_order`, `process_refund` y `escalate_to_human`. La meta del escenario es un first-contact resolution alto (el guide habla de 80%+) y, al mismo tiempo, saber cuándo escalar a una persona.

Los dominios primarios son Agentic Architecture & Orchestration, Tool Design & MCP Integration y Context Management & Reliability.

Claude elige la siguiente tool. Esta carpeta no le deja decidir el permiso ni el dinero:

- El bucle sigue solo cuando `stop_reason` es `tool_use` y para en `end_turn`. Un texto del asistente, aunque diga que el caso terminó, no cierra el ciclo. El tope de 8 turnos es un riel, no la parada correcta.
- Antes de `lookup_order` y de `process_refund` tiene que haber un solo cliente activo verificado. Si el correo coincide con dos personas, no se elige una. Una cuenta `restricted` no queda verificada. Cero filas es una consulta bien hecha, no un fallo.
- Un reembolso por encima de 500 USD lo niega un hook `PreToolUse`. No se reintenta: se escala con el importe exacto. 500 USD exactos sí pueden pasar. El prompt no autoriza el movimiento.
- La ventana de devolución, la moneda y un reembolso ya registrado los decide PostgreSQL.
- Quien recibe el escalamiento no ve el transcript. `escalate_to_human` le deja el customer id, el order id, el importe, el root cause y la recommended action.
- `PostToolUse` deja los pedidos en una sola forma: el status numérico pasa a placed, shipped o delivered, y la fecha llega como ISO o como unix. Se quitan el payment token, la dirección y el sku. Los case facts guardan cada id, importe, moneda y fecha, sin redondear ni resumir.
- Cada error trae `errorCategory`, `isRetryable`, `partialResults` y `attemptedQuery`. `transient` se puede reintentar. `validation`, `permission` y `business` no.

La semilla de `escenario_01` deja casos para recorrer ese flujo:

| Caso | Qué tiene que pasar |
| --- | --- |
| `ana@example.test`, `ord_10`, 42.50 USD | Camino feliz. La ventana sigue abierta. |
| Ana, `ord_11`, 780.00 USD | Pasa el tope de 500 USD. Hay que escalar. |
| Ana, `ord_12`, 15.00 USD | Pedido de 2020. La ventana está cerrada. |
| `shared@example.test` | Dos clientes. No se escoge uno. |
| `restricted@example.test` | Cuenta restricted. No se verifica. |
| `beatriz@example.test` | Cliente activo y sin pedidos. |
| `mateo@example.test`, `ord_20`, 20.00 EUR | El reembolso automático es solo USD. |
| `ord_30` | Ya tiene el reembolso `ref_ord_30`. |

Los pedidos, clientes, pagos y reembolsos viven en PostgreSQL, base `ccar_f`, esquema `escenario_01`. Los escenarios 2 a 6 tienen su esquema reservado y todavía sin tablas. La clave está en `.env` y no se escribe en el SQL ni en este archivo. `fixtures/store.json` quedó de la práctica anterior y ya no se consulta.

## Base de datos

```powershell
cd escenario-01-agente-soporte
python -m pip install "psycopg[binary]"
$env:PYTHONPATH = "src"
python -m support_agent.db_admin
```

Eso crea `ccar_f` si no existe y aplica `db/ccar_f.sql`. No borra otras bases.

Para volver a la semilla después de un reembolso, desde la misma carpeta:

```powershell
$env:PYTHONPATH = "src"
python -m support_agent.db_admin --reset
```

`--reset` vacía solo las tablas de `escenario_01` y las vuelve a cargar. No toca las otras bases ni los esquemas `escenario_02` a `escenario_06`.

## Qué corre sin Claude

Todo lo de abajo es local. `pytest` no llama a la API y no necesita `ANTHROPIC_API_KEY`.

| Pieza | Archivo | Qué entrena |
| --- | --- | --- |
| Bucle `tool_use` / `end_turn` | `src/support_agent/loop.py` | Task 1.1. Para en `end_turn`. El tope de iteraciones es un riel, no la parada. |
| Gates de identidad y de 500 USD | `src/support_agent/gates.py`, `hooks.py` | Tasks 1.4 y 1.5. Un prompt no autoriza un reembolso. |
| Tools MCP | `src/support_agent/tools.py` | Tasks 2.1 y 2.2. Descripciones que no se pisan, y errores con `errorCategory`, `isRetryable`, `partialResults`, `attemptedQuery`. |
| Normalización y case facts | `normalize.py`, `session.py` | Task 5.1. Fechas e importes no se resumen ni se redondean. |
| Cuándo escalar | `prompt.py` y `escalate_to_human` | Task 5.2. La persona no ve el transcript. |

Tools del examen: `get_customer`, `lookup_order`, `process_refund`, `escalate_to_human`. `lookup_handoff` es local: comprueba el ticket y no mueve dinero.

Un resultado sin filas es éxito. Un timeout es `transient` y se puede reintentar. Una validación, un permiso o una regla de negocio no se reintentan.

## El único punto que llama a Claude

`src/support_agent/sdk_runner.py` importa `claude-agent-sdk`, arma el servidor MCP in-process y abre `ClaudeSDKClient`. Ahí viven `allowed_tools`, `disallowed_tools`, `permission_mode="dontAsk"` y los hooks `PreToolUse` / `PostToolUse`.

Ese archivo no se usa en los tests. Para una corrida real, escribe la clave en `escenario-01-agente-soporte/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-haiku-5-5
CLAUDE_MAX_OUTPUT_TOKENS=4096
```

`CLAUDE_MAX_OUTPUT_TOKENS` es el tope de salida de cada respuesta. El Agent SDK no tiene `max_tokens` en las opciones; el runner lo pasa como `CLAUDE_CODE_MAX_OUTPUT_TOKENS`. Al terminar imprime entrada, salida, caché y el costo en USD. El tope de turnos sigue en 8.

Ese archivo no se comparte. La clave es de la consola de Anthropic. Después:

```powershell
cd escenario-01-agente-soporte
python -m pip install -e ".[claude]"
python soporte.py
```

Sin argumentos, el cliente es Ana y el pedido es `ord_10`. Para otro caso: `python soporte.py "Mi correo es beatriz@example.test."` Para seguir en la misma sesión: `python soporte.py --chat`. Una línea vacía cierra. El tope de 8 son turnos del modelo, no tools. `pytest` comprueba que el octavo `end_turn` sí cierra y que un noveno turno no se ejecuta.

La salida pinta al cliente, al agente, la frase corta de por qué llama la tool, y la tool con sus ids. El handoff no abre un chat con una persona. Si el reembolso pasa de 500 USD, el hook niega el dinero y graba una sola fila por pedido en `escenario_01.handoffs`. `lookup_handoff` revisa si ese ticket ya existe. Si existe, no se crea otro: se le dice al cliente que espere o que pregunte a soporte. `ord_11` son 780 USD: 700 de los audífonos y 80 del estuche.

Si `CLAUDE_MODEL` no está en `.env`, el runner usa `claude-haiku-4-5`. Si falta `CLAUDE_MAX_OUTPUT_TOKENS`, el tope es 4096. Confirma el id del modelo en la consola de Anthropic antes de dejarlo corriendo.

`allowed_tools` solo auto-aprueba. No esconde las tools de Claude Code. Por eso el runner niega Read, Write, Edit, Bash y el resto de built-ins. El agente usa las cuatro tools del examen y, además, `lookup_handoff` para no abrir otro ticket del mismo pedido.

## Tests

```powershell
cd escenario-01-agente-soporte
python -m pip install pytest
$env:PYTHONPATH = "src"
python -m pytest
```

`pyproject.toml` ya pone `src` en el `pythonpath` de pytest. La variable sobra si invocas `python -m pytest` dentro de esta carpeta.
