# Qué enseña el escenario 1

Notas de este folder. El Exam Guide v1.0, en `docs/`, sigue siendo la fuente. Aquí no hay preguntas inventadas: está lo que el código ya hace y lo que conviene volver a leer.

El escenario es un Customer Support Resolution Agent. Claude elige la siguiente tool. El permiso, el dinero y la identidad no se le dejan al prompt.

## La idea que hay que llevarse

Un prompt guía. Un hook niega. PostgreSQL guarda.

Si la regla vive solo en `prompt.py`, el modelo puede saltársela. En este caso la identidad y el tope de 500 USD están en `gates.py` y `hooks.py`. La ventana de devolución, la moneda y el reembolso ya emitido están en `backend.py`. El texto del sistema dice qué hacer después, no autoriza el movimiento.

Eso es el centro de las tasks 1.4 y 1.5. El resto del folder existe para que esa frase se pueda señalar en un archivo.

## El bucle

`loop.py` es la task 1.1, sin red.

- Sigue solo cuando `stop_reason` es `tool_use`.
- Para solo cuando `stop_reason` es `end_turn`.
- Una frase del asistente, aunque diga que el caso terminó, no cierra el ciclo.
- Si el turno ya es `end_turn`, las tool calls que vengan en ese mismo turno no se ejecutan.
- `DEFENSIVE_TURN_CAP` es 8. Llegar ahí sin `end_turn` es `SafetyCapExceeded`. El tope es un riel, no la señal de que el trabajo está listo.

`tests/test_scenario.py` recorre esas cuatro frases con un `ModelClient` falso. Por eso `pytest` no gasta créditos.

## De dónde sale `stop_reason`

`stop_reason` lo escribe la Claude API en cada respuesta de `POST /v1/messages`. No lo inventa este repo ni el Claude Agent SDK. El SDK, en `sdk_runner.py`, lee ese mismo campo por dentro. `loop.py` lo lee a mano para poder estudiarlo sin red.

`end_turn` y `tool_use` son valores de ese campo, no funciones. `tool_use` pide ejecutar una tool y seguir. `end_turn` dice que la respuesta ya acabó: ese texto es el que ve el cliente. Una frase como "ya terminé" no sustituye el campo.

Esta muestra es real, con Ana y `ord_10`. El prompt pedía el total y prohibía reembolsar. No se llamó a `process_refund` y no se movió dinero. Fueron tres respuestas. En las dos primeras el bucle tiene que seguir. En la tercera para. Se omitió un bloque `thinking`: a veces la API lo manda, con una firma larga, y no es la señal de parada.

Respuesta 1. Pide identificar a Ana. `stop_reason` es `tool_use`.

```json
{
  "id": "msg_011CgVPxuGXwLQsnNRZuwcWH",
  "type": "message",
  "role": "assistant",
  "model": "claude-haiku-5-5",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_015S2MnzoCgtzoZBneK486pb",
      "name": "get_customer",
      "input": { "email": "ana@example.test" }
    }
  ],
  "stop_reason": "tool_use",
  "stop_sequence": null,
  "usage": { "input_tokens": 522, "output_tokens": 111 }
}
```

Respuesta 2. Ana ya está verificada y pide el pedido. Sigue en `tool_use`. El programa ejecuta `lookup_order`, mete el resultado en el historial y llama otra vez.

```json
{
  "id": "msg_011CgVPxzuMxzkDxW3SUX61c",
  "type": "message",
  "role": "assistant",
  "model": "claude-haiku-5-5",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_018XE4cEa3D4u5yjVvrwFUak",
      "name": "lookup_order",
      "input": { "order_id": "ord_10", "customer_id": "cus_100" }
    }
  ],
  "stop_reason": "tool_use",
  "stop_sequence": null,
  "usage": { "input_tokens": 767, "output_tokens": 81 }
}
```

Respuesta 3. Ya hay texto para el cliente. `stop_reason` es `end_turn`. Aquí `loop.py` regresa.

```json
{
  "id": "msg_011CgVPy5kpTT6Y9vZZggxtJ",
  "type": "message",
  "role": "assistant",
  "model": "claude-haiku-5-5",
  "content": [
    {
      "type": "text",
      "text": "El pedido ord_10 tiene un total de 42.50 USD. No he hecho ningún reembolso."
    }
  ],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": { "input_tokens": 1106, "output_tokens": 93 }
}
```

`stop_sequence` en `null` significa que no se definió un texto propio para cortar la salida. El 8 de `DEFENSIVE_TURN_CAP` no aparece en este JSON. Es un corte de nuestro código, y del SDK vía `max_turns`, por si `end_turn` nunca llega.

## Cómo elige la tool

`tools.py` guarda una descripción por tool. Esa descripción es el mecanismo de selección: qué entra, qué sale, cuándo usarla y cuándo no. Si dos descripciones dicen lo mismo, el modelo las confunde.

| Tool | Para qué es | Qué no hace |
| --- | --- | --- |
| `get_customer` | Identificar. Email o `customer_id`. | No busca pedidos ni mueve dinero. |
| `lookup_order` | Leer el pedido después de `get_customer`. | No verifica identidad ni reembolsa. El hook lo bloquea antes. |
| `process_refund` | Reembolsar cuando la identidad ya está verificada. | No busca al cliente. |
| `escalate_to_human` | Dejar un paquete para una persona que no ve el transcript. | No es un chat con soporte. |
| `lookup_handoff` | Mirar si ese `order_id` ya tiene ticket. | No es tool del examen. No crea la fila ni mueve dinero. |

El modelo ve los nombres como `mcp__support__get_customer`. `short_tool_name` se queda con el último tramo para que el mismo gate sirva en el bucle local y en el SDK.

Cero filas es éxito. `errors.py` no marca `isError` en una búsqueda vacía. Un fallo sí trae `errorCategory`, `isRetryable`, `partialResults` y `attemptedQuery`.

| Categoría | ¿Se reintenta? | Ejemplo de este caso |
| --- | --- | --- |
| `transient` | Sí, la misma consulta. | Timeout de PostgreSQL. |
| `validation` | No. | Falta `order_id`, importe o `reason`. |
| `permission` | No. | Identidad sin verificar, otro cliente, cuenta `restricted`. |
| `business` | No. | Más de 500 USD, ventana cerrada, moneda que no es USD, pedido ya reembolsado, ticket ya abierto. |

`isRetryable: false` significa no llamar otra vez la misma tool con los mismos argumentos. Reintentar un tope de dinero es el fallo que el hook quiere evitar.

## Identidad antes de leer y antes del dinero

`session.py` verifica solo si hay exactamente un match y `account_status` es `active`.

- `shared@example.test` devuelve dos clientes. No se elige uno.
- `restricted@example.test` devuelve una fila y no queda verificado.
- Sin esa verificación, `lookup_order` y `process_refund` no corren: `pre_tool_decision` niega y `hook_denial_result` devuelve el error.
- Un pedido de otro cliente, como `ord_20` de Mateo mientras la sesión es de Ana, vuelve como `permission` y no entra al contexto.

El cliente del argumento tiene que ser el mismo que quedó verificado. Pasar `cus_100` en el JSON no sustituye a `get_customer`.

Cada turno del bucle local recibe un bloque `caseFacts` al inicio, armado de nuevo desde la sesión. No va mezclado en un resumen. En el runner, el mismo bloque viaja en el resultado de cada tool.

## El tope de 500 USD

`AUTO_REFUND_LIMIT` es `Decimal("500.00")`. 500 exactos pueden pasar. Por encima, la categoría es `business` y no es reintentable.

El hook niega antes de que el tool escriba el reembolso. Además graba el handoff en ese mismo rechazo. Si el modelo solo explica el bloqueo y no llama `escalate_to_human`, la fila igual queda. Eso se vio con `ord_11`: 700 de los audífonos más 80 del estuche son 780 USD. El dinero no salió, y al principio tampoco el ticket, porque negar y escalar eran dos pasos. Ahora el rechazo del tope llama `record_cap_handoff`.

Un importe inválido o que falta no lo decide el hook. Pasa al tool y vuelve como `validation`.

## Qué sí escala y qué no

Escalar no es "cualquier cosa que salió mal".

| Situación | Reembolso | Handoff automático |
| --- | --- | --- |
| `ord_10`, 42.50 USD, Ana verificada, ventana abierta | Sí. `ref_ord_10`. | No. El resumen dice que no hizo falta. |
| `ord_11`, más de 500 USD | No. | Sí. Una fila por pedido. |
| `ord_12`, ventana cerrada | No. `business`. | No. |
| `ord_20`, 20.00 EUR | No. Solo USD. | No. |
| `ord_30`, ya reembolsado | No. `already_refunded`. | No. |
| Cuenta restricted o correo ambiguo | No. `permission`. | No. |
| El cliente pide una persona | El caso puede ser fácil. | Sí, si el modelo llama `escalate_to_human`. El prompt lo pide. El código no lo adivina. |

Quien recibe el escalamiento no ve el transcript. El paquete lleva `customer_id`, `order_id`, `refund_amount`, `root_cause`, `reason`, `recommended_action` y `caseFacts`. Los importes, fechas e ids se copian. No se redondean ni se resumen. Eso es la task 5.1 en `normalize.py` y `session.snapshot()`, y la task 5.2 en `escalate_to_human`.

`PostToolUse` normaliza el pedido después de `lookup_order`: el status numérico pasa a placed, shipped o delivered, la fecha unix del canal legacy pasa a ISO, y se quitan payment token, dirección, sku y warehouse.

## Un ticket por compra

Cada `python soporte.py` empieza con un `SessionState` vacío. La charla de la corrida anterior no existe. PostgreSQL sí.

La primera versión deduplicaba solo en esa sesión. Otra pregunta por el mismo artículo insertaba otra fila en `escenario_01.handoffs`. Ahora `save_handoff` busca el `order_id`. Si ya hay fila, devuelve la más antigua con `already_open` y no inserta.

`lookup_handoff` es la tool para que el modelo lo diga en voz alta: el ticket existe, el cliente espera o pregunta a soporte, y no se llama otra vez a `escalate_to_human`. La garantía no es esa tool. Si el modelo se la salta, `save_handoff` igual no crea la segunda fila.

Las filas viejas del mismo pedido se quedan. No hay un índice único, porque borrarlas cambiaría la base que ya probaste. Una consulta nueva no agrega otra.

## Lo que la corrida real nos mostró

Estas tres no salen de leer el prompt. Salieron de mirar la base después.

1. El tool dijo `ref_ord_10` y la otra conexión no veía la fila. El primer `SELECT` dejaba una transacción abierta y `close()` hacía rollback. `connect()` ahora usa `autocommit=True`. Los tests siguen haciendo `BEGIN` y `rollback()`, así que no ensucian la semilla.
2. Negar el reembolso de 780 USD no es lo mismo que dejar el handoff. El hook tiene que escribir la fila, no solo devolver el texto de deny.
3. `allowed_tools` solo auto-aprueba. No esconde Read, Write, Edit ni Bash. Por eso van en `disallowed_tools`. `permission_mode` es `dontAsk`.

El deny del SDK tiene esta forma: `hookSpecificOutput.hookEventName` = `PreToolUse`, `permissionDecision` = `deny`, `permissionDecisionReason` con el motivo. El matcher escucha `process_refund` y también `mcp__support__process_refund`.

## Dónde está Claude y dónde no

| Se estudia con `pytest`, sin API | Solo corre con `python soporte.py` |
| --- | --- |
| `loop.py`, `gates.py`, `hooks.py`, `tools.py`, `errors.py`, `normalize.py`, `session.py`, `backend.py` | `sdk_runner.py` y `soporte.py` |

El runner abre `ClaudeSDKClient`, no un `query()` de una sola llamada. Carga `.env` antes de mirar `ANTHROPIC_API_KEY`. El modelo sale de `CLAUDE_MODEL`. Si no está, el código usa `claude-haiku-4-5`. El tope de salida de cada respuesta es `CLAUDE_MAX_OUTPUT_TOKENS`, pasado como `CLAUDE_CODE_MAX_OUTPUT_TOKENS`. El SDK no tiene un campo `max_tokens` en las opciones, ni un techo de tokens para toda la sesión.

La clave de la consola paga el uso. No hace falta una suscripción de Claude Code. Una corrida gasta créditos. El cache read grande es el prompt de Claude Code, no el mensaje del cliente.

`python soporte.py` sigue siendo un mensaje. `python soporte.py --chat` deja la misma sesión abierta: el siguiente renglón ve el historial y los case facts. Una línea vacía cierra. Si solo llega el correo y hay varios pedidos, el agente pide cuál. No puede leer un `order_id` antes de `get_customer`.

El 8 no son ocho tools ni ocho cobros fijos. `DEFENSIVE_TURN_CAP` cuenta turnos del modelo. Cada `tool_use` gasta un turno y el bucle sigue. `end_turn` para, aunque sea el turno 8. El turno 9 no existe: sin `end_turn` a los 8, el resultado es `SafetyCapExceeded`. `pytest` lo cuenta sin API. El runner en vivo pasa el mismo 8 como `max_turns`.

## En qué orden volver a ver el código

1. `loop.py`. Marca el `if turn.stop_reason == "end_turn"` y el `raise SafetyCapExceeded` del final.
2. `tools.py`, las constantes `*_DESCRIPTION`. Pregúntate qué pasaría si dos dijeran "resuelve el caso".
3. `errors.py`. Compara `ok` con `fail`. Cero filas no es un error.
4. `gates.py`, `refund_precondition`. Identidad, cliente distinto, cuenta no activa, importe por encima de 500.
5. `hooks.py`. El deny ocurre y el tool no corre. Si el mensaje trae `automatic limit`, ahí se graba el ticket.
6. `session.py` y `normalize.py`. Qué entra a `caseFacts` y qué se tira del pedido.
7. `prompt.py`. Léelo como una guía. Tapa el archivo y comprueba que el dinero sigue bloqueado.
8. `backend.py`. `issue_refund` y `handoff_for_order`. Ahí está la regla de negocio que el modelo no debe inventar.
9. `sdk_runner.py`, `build_options`. Nombres MCP, `allowed_tools`, `disallowed_tools`, los dos matchers y el tope de salida.
10. `tests/test_scenario.py`. Cada test es un caso que el Exam Guide quiere ver comportarse igual sin el modelo.

## Qué repetir con la semilla

Desde `escenario-01-agente-soporte`, `python -m pytest` no llama a la API.

Para una corrida de pago, un mensaje por caso:

- Ana y `ord_10`: camino feliz. Tiene que quedar `ref_ord_10` y no un handoff.
- Ana y `ord_11`: sin reembolso, y el ticket de ese pedido no se duplica.
- Ana y `ord_12`: ventana cerrada, sin handoff.
- `shared@example.test`: dos matches, sin reembolso.
- `restricted@example.test`: no verificado.
- `mateo@example.test` y `ord_20`: EUR, sin reembolso automático.
- El pedido que ya tiene `ref_ord_30`: error de negocio, sin handoff nuevo.

`--reset` vacía las tablas de `escenario_01` y vuelve a cargar la semilla. Borra también los reembolsos y los tickets que ya probaste. No hace falta para repasar el código.

## Qué deja este escenario fuera

Los dominios con más peso alrededor de este folder son Agentic Architecture & Orchestration, Tool Design & MCP Integration y Context Management & Reliability. Claude Code y el diseño de prompts aparecen en el borde: built-ins negados, y un system prompt que no sustituye al hook.

`lookup_handoff` no está en la lista oficial de cuatro tools. Sirve para la práctica de "no abras otro ticket". En una respuesta de examen, las cuatro siguen siendo `get_customer`, `lookup_order`, `process_refund` y `escalate_to_human`.

Los esquemas `escenario_02` a `escenario_06` están vacíos a propósito. El siguiente repaso, cuando toque otro escenario, sale otra vez del Exam Guide, no de inventar el flujo encima de este.
