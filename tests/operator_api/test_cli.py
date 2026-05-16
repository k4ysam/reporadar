import pytest

from src.operator_api.cli import main


def test_cli_help_prints_v2_commands(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("scan-repos", "scan-hackathons", "evaluate", "run", "submit", "serve", "daemon", "verify-env"):
        assert cmd in out


def test_cli_no_args_returns_zero():
    rc = main([])
    assert rc == 0


def test_submit_has_channels_flag_not_evaluate_flag(capsys):
    """submit no longer takes --evaluate (skipping evaluation is now the
    default) but does take --channels for picking which posts to generate."""
    with pytest.raises(SystemExit):
        main(["submit", "--help"])
    out = capsys.readouterr().out
    assert "--channels" in out
    assert "--evaluate" not in out
