import pytest
import requests

from protosaurus import Context, cli

if __name__ == "__main__":
    pytest.main()


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = responses
        self.verify = True
        self.requested = []

    def get(self, url):
        self.requested.append(url)
        return self._responses[url]


@pytest.fixture
def clean_cli(monkeypatch):
    """Reset the module-level globals so tests do not contaminate each other."""
    monkeypatch.setattr(cli, "_schema_cache", {})
    monkeypatch.setattr(cli, "_session", None)
    return cli


def _install_session(monkeypatch, session):
    monkeypatch.setattr(cli, "_get_session", lambda verify_ssl: session)


def test_get_schema_by_id_success(clean_cli, monkeypatch):
    session = _FakeSession(
        {
            "http://reg/schemas/ids/1": _FakeResponse(
                {"schema": 'syntax = "proto3"; message M { int32 v = 1; }'}
            )
        }
    )
    _install_session(monkeypatch, session)

    ctx = clean_cli._get_schema_by_id("http://reg", 1)

    assert ctx.message_type_from_index("<<<MAIN>>>", [0]) == "M"


def test_schema_is_cached_after_success(clean_cli, monkeypatch):
    """A successful fetch is cached, so the registry is queried only once."""
    session = _FakeSession(
        {
            "http://reg/schemas/ids/1": _FakeResponse(
                {"schema": 'syntax = "proto3"; message M { int32 v = 1; }'}
            )
        }
    )
    _install_session(monkeypatch, session)

    first = clean_cli._get_schema_by_id("http://reg", 1)
    second = clean_cli._get_schema_by_id("http://reg", 1)

    assert first is second
    assert session.requested == ["http://reg/schemas/ids/1"]


def test_get_schema_by_id_raises_on_http_error(clean_cli, monkeypatch):
    session = _FakeSession({"http://reg/schemas/ids/9": _FakeResponse({}, status_code=404)})
    _install_session(monkeypatch, session)

    with pytest.raises(requests.HTTPError):
        clean_cli._get_schema_by_id("http://reg", 9)


def test_failed_lookup_is_not_cached(clean_cli, monkeypatch):
    """A failed fetch must not leave a half-built Context in the cache."""
    session = _FakeSession({"http://reg/schemas/ids/9": _FakeResponse({}, status_code=500)})
    _install_session(monkeypatch, session)

    with pytest.raises(requests.HTTPError):
        clean_cli._get_schema_by_id("http://reg", 9)

    assert 9 not in clean_cli._schema_cache


def test_get_schema_raises_on_http_error(clean_cli, monkeypatch):
    session = _FakeSession(
        {"http://reg/subjects/s/versions/1": _FakeResponse({}, status_code=404)}
    )
    _install_session(monkeypatch, session)

    with pytest.raises(requests.HTTPError):
        clean_cli._get_schema("http://reg", "n.proto", "s", 1, Context())
