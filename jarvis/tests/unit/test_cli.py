import pytest

from jarvis import cli
from jarvis.services.spotify import APPROVED_SPOTIFY_SCOPES


def test_spotify_authorize_routes_to_safe_url_constructor(monkeypatch, capsys):
    called = {}

    def fake(configuration, *, transaction, allow_pending_authorization):
        called.update(configuration=configuration, transaction=transaction,
                      allow_pending_authorization=allow_pending_authorization)
        return "https://accounts.spotify.com/authorize?state=secret-state&code_challenge=secret-challenge"

    monkeypatch.setattr(cli, "create_spotify_authorization", fake)
    assert cli.main(["spotify", "authorize"]) == 0
    output = capsys.readouterr().out
    assert "secret-state" not in output
    assert "secret-challenge" not in output
    assert "constructed" in output.lower()
    assert called["transaction"].session_id
    assert called["allow_pending_authorization"] is True


def test_spotify_authorize_does_not_execute_browser_or_callback(monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_spotify_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "webbrowser", pytest.fail, raising=False)
    assert cli.main(["spotify", "authorize"]) == 1
    assert "autorización" in capsys.readouterr().err.lower()


def test_spotify_live_mode_is_explicit_and_reports_safe_status(monkeypatch, capsys):
    from jarvis.services.spotify import OAuthErrorCode, OAuthResult

    called = {}
    monkeypatch.setattr(cli, "run_spotify_live_authorization", lambda *args, **kwargs: (
        called.update(kwargs=kwargs) or OAuthResult(OAuthErrorCode.NETWORK_TIMEOUT, "timeout")
    ))
    assert cli.main(["spotify", "authorize", "--live"]) == 1
    assert "timeout" in capsys.readouterr().err
    assert callable(called["kwargs"]["browser_opener"])
    assert callable(called["kwargs"]["server_factory"])


def test_existing_setup_spotify_alias_remains_routed(monkeypatch):
    monkeypatch.setattr(cli, "_handle_spotify_setup", lambda: 7)
    assert cli.main(["spotify", "setup"]) == 7
