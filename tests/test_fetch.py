import types
from pathlib import Path

from pipeline import fetch as fetch_mod


def _stub_load_yaml(monkeypatch):
    """Patch ``_load_yaml`` to avoid touching the real filesystem."""
    cfg_yaml = {
        "requests": {
            "baseUrl": "https://example.com",
            "headers": {},
            "sleepSecondsMin": 0,
            "sleepSecondsMax": 0,
        }
    }
    api_yaml = {
        "mlb": {
            "eventGroupId": 1,
            "categories": {
                "Hits": {
                    "categoryId": 10,
                    "subCategories": {
                        "Total Bases": {"subCategoryId": 100},
                    },
                }
            },
        }
    }

    def _fake_loader(path: Path):  # noqa: D401
        if "config" in str(path):
            return cfg_yaml
        return api_yaml

    monkeypatch.setattr(fetch_mod, "_load_yaml", _fake_loader, raising=True)


class _FakeResp:  # noqa: D101
    def __init__(self, payload):
        self._payload = payload

    def json(self):  # noqa: D401
        return self._payload

    def raise_for_status(self):  # noqa: D401
        return None


class _FakeSession(types.SimpleNamespace):  # noqa: D101
    def __init__(self, payload):
        super().__init__(headers={})
        self._payload = payload

    def get(self, url):  # noqa: D401
        self.last_url = url
        return _FakeResp(self._payload)


def test_fetch_main(monkeypatch):
    """fetch_main should return mapping ``cat/subcat`` → payload dict."""
    _stub_load_yaml(monkeypatch)

    dummy_payload = {"selections": []}
    monkeypatch.setattr(
        fetch_mod,
        "_build_session",
        lambda cfg: _FakeSession(dummy_payload),
        raising=True,
    )

    # eliminate sleeps/randomness
    monkeypatch.setattr(fetch_mod.random, "uniform", lambda *_: 0)
    monkeypatch.setattr(fetch_mod.time, "sleep", lambda *_: None)

    result = fetch_mod.fetch_main()

    # Expect exactly one key → 'hits/total'
    assert list(result) == ["hits/total"]
    assert result["hits/total"] == dummy_payload
