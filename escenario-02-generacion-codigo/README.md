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

`format_price` pierde el cero de `19.90` y lo muestra como `19.9`. El fallo está en esa función. Arreglarlo es ejecución directa, y el archivo que cambia es `end/catalogo/precios.py`.

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

## Cómo probarlo

Desde esta carpeta:

```powershell
python -m pytest
```

Eso no usa `ANTHROPIC_API_KEY`. Las pruebas del catálogo importan `catalogo` una vez desde `start/` y otra desde `end/`. Hoy las dos copias deben dar `19.9` y el texto de `end/catalogo/` debe ser igual al de `start/catalogo/`. Si un cambio queda solo en `end/`, fallan la prueba de `end` y la de igualdad. `start/` sigue en verde.

Las notas de qué juzga el examen están en [APRENDIZAJE.md](APRENDIZAJE.md).
