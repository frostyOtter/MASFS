"""M1 entry-point configuration and credential boundaries."""

from mas_kraken.__main__ import main


def test_missing_configuration_fails_before_provider_is_called(monkeypatch, capsys):
    for name in ("MASFS_BASE_URL", "MASFS_API_KEY", "MASFS_MODEL"):
        monkeypatch.delenv(name, raising=False)

    status = main()

    assert status != 0
    assert capsys.readouterr().err


def test_configuration_is_read_at_startup_and_never_echoes_key(monkeypatch, capsys):
    import mas_kraken.__main__ as entry

    monkeypatch.setenv("MASFS_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("MASFS_API_KEY", "do-not-print-this-key")
    monkeypatch.setenv("MASFS_MODEL", "example-model")
    monkeypatch.setattr(entry, "make_openai_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(entry, "run_repl", lambda model: 0)

    assert main() == 0
    captured = capsys.readouterr()
    assert "do-not-print-this-key" not in captured.out + captured.err
