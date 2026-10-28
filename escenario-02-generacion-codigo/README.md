# Escenario 2: Code Generation with Claude Code

Práctica del escenario 2 del Exam Guide v1.0. No es una pregunta oficial.

Claude Code es el producto de línea de comandos que lee este proyecto, aplica `CLAUDE.md` y puede entrar en plan mode antes de editar. Plan mode es ese modo: mira el código y deja un plan cuando el cambio es grande o todavía hay que elegir un diseño. La ejecución directa edita ya, cuando el fallo está en una sola función. Ninguno de los dos es un campo de la Messages API. `stop_reason` sigue siendo la señal de la API del escenario 1, en `loop.py` de esa carpeta.

## Si no tienes la suscripción de Claude Code

La Messages API, la de `POST /v1/messages`, puede escribir o corregir código. No hace este escenario. No carga `CLAUDE.md`, no conoce los slash commands de `.claude/commands/`, no aplica las reglas con `paths` y no tiene plan mode ni el subagente Explore.

Explore es un subagente de Claude Code: hace la búsqueda larga y devuelve un resumen, para que el hilo principal no se llene de archivos. Un slash command es un prompt guardado en `.claude/commands/` que el equipo invoca con `/nombre`.

Por eso esta carpeta no llama a la API. Lo que el examen pide juzgar está en los archivos y en `choose_workflow`. Si más adelante instalas el CLI de Claude Code, la misma clave de consola puede pagarlo. Esta práctica no lo necesita.

## Qué hay aquí

El catálogo de juguete está dos veces.

- `start/catalogo/` es el original. No se edita.
- `end/catalogo/` empieza igual. Ahí se escribe cualquier cambio.

Hay cinco fallos, cada uno con su prueba en `end/tests/`. Arreglar uno solo, ya localizado, es ejecución directa. Pedir los cinco juntos toca `precios.py`, `fechas.py` y `pedidos.py`: eso es plan mode, el modo de Claude Code que planea antes de editar varios archivos.

`CLAUDE.md` lo dice siempre. `.claude/rules/no-editar-start.md` lo repite con `paths: ["start/**/*"]`, así la regla entra justo cuando alguien abre un archivo de `start/`. Después de una sesión de Claude Code, compara las dos carpetas. Si `start/` cambió, la instrucción no se cumplió.

| Archivo | Task del guide | Para qué mirarlo |
| --- | --- | --- |
| `CLAUDE.md` | 3.1 | Reglas del proyecto, compartidas en git. |
| `.claude/rules/pruebas.md` | 3.3 | Regla con `paths`, solo al editar un `test_*.py`. |
| `.claude/commands/arreglar.md` | 3.2 | Slash command del equipo, con un ejemplo de entrada y salida. |
| `.claude/skills/explorar/SKILL.md` | 3.2 | Skill con `context: fork` y `allowed-tools`. |
| `src/estudio/workflow.py` | 3.4 | Elige `plan_mode` o `direct_execution`. |
| `src/estudio/scratchpad.py` | 5.4 | Anota el hallazgo en un archivo para la pregunta siguiente. |

`memory_scope` distingue tres `CLAUDE.md`. El de `~/.claude/CLAUDE.md` es del usuario y no se comparte. El de la raíz del proyecto sí. Uno dentro de una subcarpeta vale solo para esa parte.

El esquema `escenario_02` en PostgreSQL sigue vacío. Este caso no guarda pedidos.

## Caso de uso

Se practica una corrección chica con Claude Code y se mira si obedeció la regla del proyecto. `start/catalogo/` es el original y no se toca. `end/catalogo/` es la copia de trabajo: empieza igual y ahí debe quedar el cambio. Al terminar la prueba, lo que haya quedado en `end/` se borra y se vuelve a copiar desde `start/`, para que la siguiente prueba empiece limpia.

1. Desde esta carpeta, carga la clave sin imprimirla y abre Claude Code. Claude Code es el programa de terminal. La clave es la de la consola, la misma del escenario 1. Cada sesión gasta créditos.

```powershell
Get-Content ..\escenario-01-agente-soporte\.env | ForEach-Object {
  if ($_ -match '^\s*ANTHROPIC_API_KEY=(.+)$') { $env:ANTHROPIC_API_KEY = $matches[1].Trim('"') }
}
claude
```

2. Pide que deje verdes las pruebas de `end/tests/` sin editarlas y sin tocar `start/`. Cada archivo de esa carpeta es un issue:

| Prueba en `end/tests/` | Función | Hoy | Debe quedar |
| --- | --- | --- | --- |
| `test_formato_precio.py` | `format_price` | `19.9` | `"19.90"` |
| `test_descuento.py` | `discounted_price` | `1.99`, solo la tajada | `Decimal("17.91")` |
| `test_fecha.py` | `label_day` | `2026-1-5` | `"2026-01-05"` |
| `test_ventana.py` | `window_is_open` | el día 30 está cerrado | el día 30 sigue abierto; el 31 no |
| `test_pedido.py` | `describe` | `19.9 @ 2026-10-28` | `"2026-10-28 19.90"` |

Para un solo issue puedes usar `/arreglar` con la función y el ejemplo de su prueba. `/arreglar` es el slash command de `.claude/commands/arreglar.md`.

3. Cierra Claude Code y corre las dos suites. No usan la API.

```powershell
git diff -- start end
python -m pytest
python -m pytest end/tests
```

`python -m pytest` solo lee `tests/`. Esa suite vigila `start/` y debe seguir en verde. Si `start/` aparece en el diff, la regla no se cumplió.

`python -m pytest end/tests` es el set que debe pasar. Antes del arreglo fallan las cinco pruebas de los issues. En `test_ventana.py` el día 31 ya pasa, para que el arreglo no deje la ventana abierta siempre. Cada issue pasa cuando su función quedó corregida en `end/catalogo/`. `test_pedido.py` también necesita el formato del precio y el de la fecha. Esas pruebas no se editan para ponerlas verdes.

4. Cuando ya viste el resultado, borra solo el código de trabajo y restaura `end/catalogo` desde `start/`. No borres `start/` ni `end/tests/`.

```powershell
Remove-Item -Recurse -Force .\end\catalogo
Copy-Item -Recurse .\start\catalogo .\end\catalogo
python -m pytest
python -m pytest end/tests
```

`tests/` vuelve a pasar. `end/tests` vuelve a fallar, porque la copia otra vez tiene el defecto. No hace falta commitear lo que Claude escribió en `end/catalogo` durante la prueba.

Las notas de qué juzga el examen están en [APRENDIZAJE.md](APRENDIZAJE.md).
