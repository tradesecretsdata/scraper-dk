import re
from types import SimpleNamespace

import pipeline.fetch as fetch


# ---------------------------------------------------------------------------
# Pure helper tests ----------------------------------------------------------
# ---------------------------------------------------------------------------


def test_slugify_basic_cases():
    """slugify should lower‑case, strip special chars, and dash‑separate words."""

    cases = {
        "Total Bases (OU)": "total-bases-ou",
        "RBI/HR - Player": "rbihr-player",
        # '+' is removed and words are dash‑joined
        "Walks+Hits / 9 Innings": "walks-hits-9-innings",
        "  Extra  Spaces  ": "extra-spaces",
    }

    for original, expected in cases.items():
        assert fetch.slugify(original) == expected


def test_utc_stamp_format():
    """utc_stamp should return YYYYMMDD-HHMMSS (UTC) with digits only."""

    stamp = fetch.utc_stamp()
    assert re.fullmatch(r"\d{8}-\d{6}", stamp), stamp


def test_build_session_sets_headers_and_timeout(monkeypatch):
    """build_session should copy headers and inject default timeout."""

    cfg = {
        "headers": {"User-Agent": "pytest-agent"},
        "retriesMax": 1,
        "timeout": 5,
    }

    captured: dict[str, object] = {}

    def fake_request(self, method, url, **kwargs):  # noqa: ANN001
        captured.update(kwargs)
        return SimpleNamespace(status_code=200, json=lambda: {})

    # Patch *before* building the session so the wrapped method is our fake
    import requests  # local import to ensure real requests is available

    monkeypatch.setattr(requests.Session, "request", fake_request, raising=True)

    sess = fetch.build_session(cfg)

    # Headers should be copied
    assert sess.headers["User-Agent"] == "pytest-agent"

    # The wrapped request should default the timeout to cfg["timeout"]
    sess.request("GET", "https://example.com")
    assert captured.get("timeout") == 5
