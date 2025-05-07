import handler


def test_lambda_handler_success(monkeypatch):
    """lambda_handler should return {"status": "ok"} when fetch_main succeeds."""

    called = {}

    def fake_main():
        called["ran"] = True

    # Patch the fetch_main symbol that was imported in handler.py
    monkeypatch.setattr(handler, "fetch_main", fake_main)

    result = handler.lambda_handler({}, None)

    assert result == {"status": "ok"}
    assert called.get("ran") is True


def test_lambda_handler_error(monkeypatch):
    """lambda_handler should catch exceptions and return an error payload."""

    def fake_main():
        raise RuntimeError("boom")

    monkeypatch.setattr(handler, "fetch_main", fake_main)

    result = handler.lambda_handler({}, None)

    assert result["status"] == "error"
    assert result["error"] == "boom"
