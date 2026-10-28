from estudio.scratchpad import read_findings, record


def test_findings_survive_in_the_file(tmp_path) -> None:
    notes = tmp_path / "notas" / "hallazgos.md"
    record(notes, "format_price vive en src/catalogo/precios.py")
    record(notes, 'Decimal("19.90") hoy se ve 19.9')
    assert read_findings(notes) == [
        "format_price vive en src/catalogo/precios.py",
        'Decimal("19.90") hoy se ve 19.9',
    ]


def test_a_missing_scratchpad_is_empty(tmp_path) -> None:
    assert read_findings(tmp_path / "no-esta.md") == []
