import pytest

from jarvis import cli
from jarvis.services.spotify import APPROVED_SPOTIFY_SCOPES


def test_spotify_authorize_routes_to_safe_url_constructor(monkeypatch, capsys):
    called = {}

    def fake(configuration, *, transaction):
        called.update(configuration=configuration, transaction=transaction)
        return "https://accounts.spotify.com/authorize?state=secret-state&code_challenge=secret-challenge"

    monkeypatch.setattr(cli, "create_spotify_authorization", fake)
    assert cli.main(["spotify", "authorize"]) == 0
    output = capsys.readouterr().out
    assert "secret-state" not in output
    assert "secret-challenge" not in output
    assert "constructed" in output.lower()
    assert called["transaction"].session_id


def test_spotify_authorize_does_not_execute_browser_or_callback(monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_spotify_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "webbrowser", pytest.fail, raising=False)
    assert cli.main(["spotify", "authorize"]) == 1
    assert "autorización" in capsys.readouterr().err.lower()


def test_existing_setup_spotify_alias_remains_routed(monkeypatch):
    monkeypatch.setattr(cli, "_handle_spotify_setup", lambda: 7)
    assert cli.main(["spotify", "setup"]) == 7
