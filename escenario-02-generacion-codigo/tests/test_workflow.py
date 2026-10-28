from pathlib import Path

from estudio.workflow import Change, choose_workflow, memory_scope


def test_one_localized_fix_is_direct_execution() -> None:
    choice = choose_workflow(Change(files=("src/catalogo/precios.py",)))
    assert choice.mode == "direct_execution"
    assert choice.explore is False


def test_many_files_use_plan_mode() -> None:
    choice = choose_workflow(
        Change(
            files=tuple(f"src/mod_{n}.py" for n in range(45)),
            verbose_discovery=True,
        )
    )
    assert choice.mode == "plan_mode"
    assert choice.explore is True


def test_two_approaches_use_plan_mode_even_in_one_file() -> None:
    choice = choose_workflow(
        Change(files=("src/catalogo/precios.py",), approaches=2, architectural=True)
    )
    assert choice.mode == "plan_mode"


def test_user_memory_is_not_the_project_file() -> None:
    assert memory_scope("~/.claude/CLAUDE.md") == "user"
    assert memory_scope("CLAUDE.md") == "project"
    assert memory_scope(".claude/CLAUDE.md") == "project"
    assert memory_scope("src/pagos/CLAUDE.md") == "directory"


def test_path_rule_names_tests_in_any_folder() -> None:
    rule = (Path(__file__).parents[1] / ".claude" / "rules" / "pruebas.md").read_text(encoding="utf-8")
    assert 'paths:' in rule
    assert '"**/test_*.py"' in rule
