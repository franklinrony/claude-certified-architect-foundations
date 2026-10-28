# Qué enseña el escenario 2

Notas de esta carpeta. El Exam Guide v1.0, en `docs/`, sigue siendo la fuente. Aquí no hay preguntas inventadas.

El escenario se llama Code Generation with Claude Code. El guide dice que el equipo genera código, refactoriza, depura y documenta con Claude Code, y que hay que integrar slash commands, `CLAUDE.md` y la elección entre plan mode y ejecución directa. Los dominios primarios son Claude Code Configuration & Workflows y Context Management & Reliability.

## La API no es este caso

La Messages API devuelve un mensaje con `stop_reason`. Eso se estudió en el escenario 1. Claude Code es otra capa: al abrir una carpeta lee `CLAUDE.md`, las reglas de `.claude/rules/`, los comandos de `.claude/commands/` y las skills de `.claude/skills/`. Plan mode y Explore son de ese producto.

Pedirle a la API "compórtate como Claude Code" no carga esos archivos ni cambia de modo. El juicio del examen es cuál de esos mecanismos usar, no cómo reimplementarlos con un `POST /v1/messages`.

## Qué decidir

Plan mode cuando el cambio toca muchos archivos, hay más de un diseño posible, o la decisión es de arquitectura. Ejecución directa cuando el arreglo es una validación o un bug de una función y ya se sabe dónde está. `format_price` es el segundo caso. El original está en `start/catalogo/precios.py` y no se toca. La corrección se escribe en `end/catalogo/precios.py`.

Esa prohibición vive en `CLAUDE.md` y en una regla con `paths`. Claude Code la lee. No es un permiso del sistema de archivos: si la desobedece, `start/` cambia y el diff lo muestra. El examen distingue una instrucción cargada por Claude Code de un control que el programa no puede saltarse.

Las pruebas no son las mismas para las dos copias. `tests/` vigila `start/` y espera los cinco defectos. `end/tests/` tiene un archivo por issue y describe el resultado correcto. Fallan hasta que el código de `end/catalogo/` cambie. No se editan esas pruebas para ponerlas verdes. Al terminar se borra `end/catalogo` y se copia desde `start/`. `end/tests/` se queda.

Explore acompaña la exploración larga dentro de plan mode. Devuelve un resumen. No reemplaza el plan ni justifica editar a ciegas.

Una convención que vale para todos los `test_*.py`, estén donde estén, va en `.claude/rules/` con `paths`. Un `CLAUDE.md` por carpeta no cubre archivos del mismo tipo repartidos por el árbol.

El `CLAUDE.md` de `~/.claude/` no entra al repositorio. Si un compañero no recibe una instrucción, el primer sitio donde mirar es si esa instrucción quedó solo en la memoria de un usuario.

El slash command `/arreglar` es del proyecto, así que viaja con git. Una skill con `context: fork` aísla una lectura ruidosa. `CLAUDE.md` se carga siempre. La skill se invoca cuando hace falta. No son lo mismo.

## El contexto largo

La task 5.4 habla de sesiones que ya no citan la clase concreta y empiezan a hablar de "el patrón típico". El scratchpad guarda el archivo y el dato exacto. La pregunta siguiente lee ese archivo. No se fía de que el modelo siga teniéndolo en el medio del contexto.

## Qué deja fuera

El flag `-p` y `--json-schema` en un pipeline son el escenario 5. Los subagentes de investigación son el escenario 3. El bucle `tool_use` / `end_turn` es el escenario 1.
