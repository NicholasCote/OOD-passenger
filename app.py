"""SAM System Status — OOD sandbox Passenger app (Flask/WSGI).

Routes:
    GET /            HTML dashboard (auto-refreshes client-side)
    GET /api/status  the assembled status payload as JSON (for live refresh)
    GET /healthz     liveness

Deployed as an OOD sandbox app: Passenger detects passenger_wsgi.py and
serves this at /pun/dev/<app>. No auth in the app itself — it assumes the
SAM status endpoints are on a public tier.
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template

from sam_client import SamStatusClient

app = Flask(__name__)
client = SamStatusClient()


def _pct(v):
    return "-" if v is None else f"{v:.0f}%"


def _system_state(s):
    """Coarse health rollup for a compute system, or None if no data."""
    if not s:
        return None
    down = (s.get("cpu_nodes_down") or 0) + (s.get("gpu_nodes_down") or 0)
    total = (s.get("cpu_nodes_total") or 0) + (s.get("gpu_nodes_total") or 0)
    login_bad = any(not n.get("available", True) for n in s.get("login_nodes", []))
    fs_bad = any(
        (not f.get("available", True)) or f.get("degraded", False)
        for f in s.get("filesystems", [])
    )
    if login_bad or (total and down / total > 0.10):
        return "degraded"
    if fs_bad or any(n.get("degraded", False) for n in s.get("login_nodes", [])):
        return "warn"
    return "ok"


def _busiest_queue(s):
    queues = (s or {}).get("queues") or []
    if not queues:
        return None
    q = max(queues, key=lambda q: q.get("pending_jobs", 0) or 0)
    return q if (q.get("pending_jobs") or 0) > 0 else None


def _assemble():
    data = client.status()
    systems = []
    for name, key in (("Derecho", "derecho"), ("Casper", "casper")):
        s = data.get(key)
        busiest = _busiest_queue(s)
        systems.append({
            "name": name,
            "state": _system_state(s),
            "present": s is not None,
            "cpu_util": _pct((s or {}).get("cpu_utilization_percent")),
            "gpu_util": _pct((s or {}).get("gpu_utilization_percent")),
            "has_gpu": bool((s or {}).get("gpu_count_total")),
            "running": (s or {}).get("running_jobs"),
            "pending": (s or {}).get("pending_jobs"),
            "users": (s or {}).get("active_users"),
            "busiest_queue": (
                {"name": busiest.get("queue_name"), "pending": busiest.get("pending_jobs")}
                if busiest else None
            ),
        })

    jh = data.get("jupyterhub")
    jupyterhub = None
    if jh:
        jupyterhub = {
            "state": "ok" if jh.get("available") else "degraded",
            "sessions": jh.get("active_sessions"),
            "users": jh.get("active_users"),
            "cpu_util": _pct(jh.get("cpu_utilization_percent")),
        }

    outages = [o for o in (data.get("outages") or []) if o.get("status") != "resolved"]
    reservations = sorted(
        data.get("reservations") or [],
        key=lambda r: str(r.get("start_time", "")),
    )

    return {
        "systems": systems,
        "jupyterhub": jupyterhub,
        "outages": outages,
        "next_reservation": reservations[0] if reservations else None,
        "source": data.get("source"),
        "fetched_at": data.get("fetched_at"),
        "errors": data.get("errors") or {},
    }


@app.route("/")
def index():
    return render_template("status.html", **_assemble())


@app.route("/api/status")
def api_status():
    return jsonify(_assemble())


@app.route("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
