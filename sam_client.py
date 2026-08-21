from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

APP_ROOT = Path(__file__).resolve().parent
MOCK_PATH = APP_ROOT / "data" / "mock_status.json"

ENDPOINTS = {
    "derecho": "/api/v1/status/derecho/latest",
    "casper": "/api/v1/status/casper/latest",
    "jupyterhub": "/api/v1/status/jupyterhub/latest",
    "outages": "/api/v1/status/outages",
    "reservations": "/api/v1/status/reservations",
}

class SamStatusClient:
    def __init__(self, base_url=None, cache_ttl=None, mock=None):
        self.base_url = (base_url or os.environ.get("SAM_STATUS_BASE_URL") or "").rstrip("/")
        self.cache_ttl = int(cache_ttl or os.environ.get("SAM_STATUS_CACHE_TTL") or 60)
        env_mock = os.environ.get("SAM_STATUS_MOCK") == "1"
        self.mock = bool(mock) or env_mock or not self.base_url
        self._cache = None          # last good payload
        self._cache_at = 0.0        # monotonic timestamp of last good fetch

    def status(self):
        if self.mock:
            return self._mock_payload()

        if self._cache is not None and (time.monotonic() - self._cache_at) < self.cache_ttl:
            return self._cache

        payload = self._fetch_live()
        if not payload["errors"] or (payload.get("derecho") and payload.get("casper")):
            self._cache = payload
            self._cache_at = time.monotonic()
            return payload
        if self._cache is not None:
            stale = dict(self._cache)
            stale["source"] = "cached"
            return stale
        fallback = self._mock_payload()
        fallback["errors"] = payload["errors"]
        return fallback

    def _fetch_live(self):
        payload = {"source": "live", "errors": {}}
        for key, path in ENDPOINTS.items():
            try:
                resp = requests.get(
                    f"{self.base_url}{path}",
                    headers={"Accept": "application/json"},
                    timeout=(3, 5),
                )
                resp.raise_for_status()
                payload[key] = resp.json()
            except (requests.RequestException, ValueError) as exc:
                payload["errors"][key] = str(exc)
                payload[key] = [] if key in ("outages", "reservations") else None
        payload["fetched_at"] = _now_iso()
        return payload

    def _mock_payload(self):
        with open(MOCK_PATH, encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["source"] = "mock"
        raw["errors"] = {}
        raw["fetched_at"] = _now_iso()
        return raw

def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
