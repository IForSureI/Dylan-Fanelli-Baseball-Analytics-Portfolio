from baseball.cli import main


def test_predictions_check_reports_fifteen_calls(capsys):
    main(["predictions", "check"])
    assert "15 calls in predictions/2027.yaml; no problems" in capsys.readouterr().out


def test_sql_list_names_every_query(capsys):
    from baseball import sqlkit

    main(["sql", "list"])
    out = capsys.readouterr().out
    assert all(n in out for n in sqlkit.queries()) and len(sqlkit.queries()) == 12


def test_advance_help_goes_to_the_module_parser(capsys):
    import pytest

    with pytest.raises(SystemExit):
        main(["advance", "--help"])
    assert "--extra" in capsys.readouterr().out
