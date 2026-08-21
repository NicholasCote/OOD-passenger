"""Smoke tests. Run: SAM_STATUS_MOCK=1 python -m pytest tests/ -q"""
import os
os.environ.setdefault("SAM_STATUS_MOCK", "1")
from app import app  # noqa: E402

def _client():
    return app.test_client()

def test_index_renders():
    r = _client().get("/")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Derecho" in body and "Casper" in body

def test_api_shape():
    j = _client().get("/api/status").get_json()
    assert j["source"] in ("mock", "live", "cached")
    assert len(j["systems"]) == 2
    assert "errors" in j

def test_healthz():
    assert _client().get("/healthz").get_json() == {"ok": True}
