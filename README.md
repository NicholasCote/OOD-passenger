# sam-status (Flask)

NCAR system status panel — Derecho, Casper, JupyterHub, active outages, and
the next reservation — read from the SAM status API (`benkirk/sam-queries`).

Built to run as an **Open OnDemand sandbox Passenger app** (Develop → My
Sandbox Apps), assuming the SAM `/api/v1/status/*` endpoints are served on a
**public / unauthenticated tier**. No credentials in the app.

```
sam-status-flask/
├── passenger_wsgi.py    # OOD/Passenger entry point (exposes `application`)
├── app.py               # Flask app: / , /api/status , /healthz
├── sam_client.py        # fetch + TTL cache + graceful degradation to mock
├── templates/status.html
├── data/mock_status.json
├── requirements.txt
├── manifest.yml         # OOD app card
├── .env.example
└── tests/test_app.py
```

## Local dev

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
SAM_STATUS_MOCK=1 python app.py      # http://127.0.0.1:8080  (bundled mock data)
# or against a real public SAM:
SAM_STATUS_BASE_URL=https://sam.k8s.ucar.edu python app.py
SAM_STATUS_MOCK=1 python -m pytest tests/ -q
```

With no `SAM_STATUS_BASE_URL` set, the app serves bundled mock data and
labels the footer `source: mock`, so it runs and demos with zero config.

## Config

| Env var | Meaning | Default |
|---|---|---|
| `SAM_STATUS_BASE_URL` | SAM webapp root, no trailing slash | (unset → mock) |
| `SAM_STATUS_CACHE_TTL` | seconds to reuse a good fetch | `60` |
| `SAM_STATUS_MOCK` | `1` forces bundled mock data | off |

Per request the client serves a fresh-enough cached payload, else fetches
all five endpoints (3 s connect / 5 s read), else falls back to the last
good cache, else the bundled mock. Every payload carries a `source` label
(`live` / `cached` / `mock`) and any per-endpoint `errors`, so the UI never
misrepresents stale or fallback data and never 500s on a SAM outage.

## Deploy to the OOD sandbox

On the OOD web node, as yourself:

```bash
git clone <repo> ~/ondemand/dev/sam-status
cd ~/ondemand/dev/sam-status
# provide Flask + requests where Passenger's Python can see them, e.g.:
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env    # set SAM_STATUS_BASE_URL, or leave unset for mock
```

Then Develop → My Sandbox Apps → **SAM System Status** → Launch. Served at
`/pun/dev/sam-status`, visible only to you.

Notes for the OOD environment:
- Passenger loads `application` from `passenger_wsgi.py`. If the app can't
  find Flask, point Passenger at the venv interpreter — set
  `PassengerPython` in the app's config, or use OOD's app-level Python
  settings — so the venv's packages are on the path.
- After editing files, restart the app: `touch tmp/restart.txt` in the app
  dir (create `tmp/` if needed).
- The client-side refresh in `status.html` fetches `api/status` (relative),
  so it resolves correctly under the `/pun/dev/sam-status/` proxy base.

## Path to a Dashboard widget

Widgets live under `/etc/ood/config/apps/dashboard/` (admin-only). This
Flask app is the standalone-Passenger equivalent — useful on its own as a
pinned app, and a working reference for an admin building the widget: the
health-rollup logic in `app.py` (`_system_state`, `_busiest_queue`) and the
card markup in `templates/status.html` port directly into an ERB partial.

## Upstream dependency

Assumes SAM serves a public status tier. If the `/api/v1/status/*` GETs are
still `@login_required`, either (a) add an unauthenticated public
serialization upstream (system-level status only; exclude any per-user
fields), or (b) set `SAM_STATUS_BASE_URL` unset and demo on mock data until
that lands. The app needs no change when the public tier appears.
