"""Optional FastAPI dashboard (run with `python server.py --dashboard 127.0.0.1:8080`)."""

from __future__ import annotations

import html
import threading
from typing import Any, Callable

SnapshotFn = Callable[[], dict[str, Any]]


def start_dashboard(bind_host: str, port: int, snapshot: SnapshotFn) -> threading.Thread:
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Dashboard requires FastAPI and uvicorn. Install: pip install -r requirements-dashboard.txt",
        ) from exc

    app = FastAPI(title="Mini DNS Resolver", docs_url=None, redoc_url=None)

    @app.get("/api/stats")
    def api_stats() -> dict[str, Any]:
        return snapshot()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        data = snapshot()
        rows = "".join(
            f"<tr><td>{html.escape(str(k))}</td><td style='text-align:right'>{html.escape(str(v))}</td></tr>"
            for k, v in sorted(data.items())
            if k != "recent"
        )
        recent = data.get("recent") or []
        recent_rows = ""
        for item in reversed(recent[-20:]):
            recent_rows += "<tr>" + "".join(
                f"<td>{html.escape(str(item.get(c, '')))}</td>" for c in ("ts", "qname", "qtype", "outcome", "latency_ms")
            ) + "</tr>"
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Mini DNS Resolver</title>
<style>body{{font-family:system-ui;margin:2rem}} table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:4px 8px}}</style>
</head><body>
<h1>Mini DNS Resolver</h1>
<p>Read-only snapshot. Bind dashboard to <code>127.0.0.1</code> in untrusted networks.</p>
<h2>Counters</h2>
<table><thead><tr><th>key</th><th>value</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Recent queries</h2>
<table><thead><tr><th>ts</th><th>qname</th><th>qtype</th><th>outcome</th><th>ms</th></tr></thead><tbody>{recent_rows}</tbody></table>
</body></html>"""

    def runner() -> None:
        uvicorn.run(app, host=bind_host, port=port, log_level="warning")

    t = threading.Thread(target=runner, name="dashboard-uvicorn", daemon=True)
    t.start()
    return t
