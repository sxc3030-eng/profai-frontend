# -*- coding: utf-8 -*-
"""Serveur de failover — AI Formateur MAT-9F.

Tourne sur le i5 local. Surveille Oracle. Si Oracle tombe → active le i5.
Si Oracle revient → redirige vers Oracle.

Usage:
    cd D:\MAT-9F
    $env:PYTHONPATH="src"
    python src/memory_agent/failover_server.py --port 9000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from aiohttp import web


# ── Configuration ────────────────────────────────────────────────────────────

@dataclass
class FailoverState:
    """État du failover."""

    active_server: str = "oracle"  # "oracle" | "i5"
    oracle_url: str = ""
    i5_url: str = "http://127.0.0.1:8100"
    oracle_healthy: bool = True
    i5_healthy: bool = True
    last_check: str = ""
    failover_count: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_server": self.active_server,
            "oracle_healthy": self.oracle_healthy,
            "i5_healthy": self.i5_healthy,
            "last_check": self.last_check,
            "failover_count": self.failover_count,
            "history": self.history[-20:],  # 20 derniers événements
        }


state = FailoverState()
routes = web.RouteTableDef()


# ── Health Check ─────────────────────────────────────────────────────────────

async def check_server(url: str, timeout: int = 10) -> bool:
    """Vérifie si un serveur est en ligne."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/api/health", timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                return resp.status == 200
    except Exception:
        return False


async def health_monitor_loop(oracle_url: str, i5_url: str, check_interval: int = 30) -> None:
    """Boucle de surveillance continue."""
    global state

    while True:
        now = datetime.now(timezone.utc).isoformat()
        state.last_check = now

        # Vérifier les deux serveurs
        oracle_ok = await check_server(oracle_url)
        i5_ok = await check_server(i5_url)

        state.oracle_healthy = oracle_ok
        state.i5_healthy = i5_ok

        previous = state.active_server

        if oracle_ok:
            # Oracle est up → toujours préférer Oracle
            if state.active_server != "oracle":
                state.active_server = "oracle"
                state.history.append({
                    "timestamp": now,
                    "event": "failback",
                    "from": previous,
                    "to": "oracle",
                    "reason": "Oracle restored",
                })
                print(f"🔄 FAILBACK  {previous} → oracle (Oracle restored)")
        elif i5_ok:
            # Oracle down, i5 up → basculer sur i5
            if state.active_server != "i5":
                state.active_server = "i5"
                state.failover_count += 1
                state.history.append({
                    "timestamp": now,
                    "event": "failover",
                    "from": previous,
                    "to": "i5",
                    "reason": "Oracle unreachable",
                })
                print(f"⚠️  FAILOVER  {previous} → i5 (Oracle unreachable)")
        else:
            # Les deux sont down
            state.history.append({
                "timestamp": now,
                "event": "both_down",
                "reason": "Oracle and i5 unreachable",
            })
            print(f"❌ BOTH DOWN  Oracle and i5 unreachable")

        await asyncio.sleep(check_interval)


# ── Endpoints ────────────────────────────────────────────────────────────────

@routes.get("/api/health")
async def health(request: web.Request) -> web.Response:
    """État du failover."""
    return web.json_response({
        "status": "ok",
        "service": "ai-formateur-failover",
        "failover": state.to_dict(),
    })


@routes.get("/api/active")
async def get_active(request: web.Request) -> web.Response:
    """Retourne l'URL du serveur actif."""
    return web.json_response({
        "active_server": state.active_server,
        "url": state.oracle_url if state.active_server == "oracle" else state.i5_url,
        "oracle_healthy": state.oracle_healthy,
        "i5_healthy": state.i5_healthy,
    })


@routes.post("/api/trigger")
async def trigger_failover(request: web.Request) -> web.Response:
    """Déclenche manuellement un failover (pour test ou urgence)."""
    data = await request.json()
    target = data.get("target", "i5")
    reason = data.get("reason", "manual")

    previous = state.active_server
    state.active_server = target
    state.failover_count += 1
    state.history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "manual_failover",
        "from": previous,
        "to": target,
        "reason": reason,
    })

    print(f"🔧 MANUAL FAILOVER  {previous} → {target} ({reason})")
    return web.json_response({"status": "ok", "active_server": target})


@routes.get("/api/history")
async def get_history(request: web.Request) -> web.Response:
    """Historique des événements de failover."""
    return web.json_response({"history": state.history})


# ── Proxy ────────────────────────────────────────────────────────────────────

@routes.route("*", "/proxy/{path:.*}")
async def proxy_to_active(request: web.Request) -> web.Response:
    """Proxy les requêtes vers le serveur actif."""
    import aiohttp

    target_url = state.oracle_url if state.active_server == "oracle" else state.i5_url
    path = request.match_info.get("path", "")
    full_url = f"{target_url}/{path}"

    try:
        async with aiohttp.ClientSession() as session:
            # Forward la requête
            method = request.method
            headers = dict(request.headers)
            headers.pop("Host", None)

            body = await request.read() if method in ("POST", "PUT", "PATCH") else None

            async with session.request(
                method, full_url, headers=headers, data=body, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                response_body = await resp.read()
                return web.Response(
                    body=response_body,
                    status=resp.status,
                    headers=dict(resp.headers),
                )
    except Exception as e:
        return web.json_response({
            "error": "proxy_failed",
            "detail": str(e),
            "active_server": state.active_server,
        }, status=502)


# ── Démarrage ────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur de failover AI Formateur")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--oracle-url", type=str, default="http://ORACLE_IP:8100",
                        help="URL du serveur Oracle principal")
    parser.add_argument("--i5-url", type=str, default="http://127.0.0.1:8100",
                        help="URL du serveur i5 local")
    parser.add_argument("--check-interval", type=int, default=30,
                        help="Intervalle de health check en secondes")
    args = parser.parse_args()

    state.oracle_url = args.oracle_url
    state.i5_url = args.i5_url

    app = web.Application()
    app.add_routes(routes)

    # Lancer la boucle de surveillance en arrière-plan
    async def on_startup(app):
        asyncio.create_task(health_monitor_loop(
            args.oracle_url, args.i5_url, args.check_interval
        ))

    app.on_startup.append(on_startup)

    print(f"🔄 Failover Server — http://{args.host}:{args.port}")
    print(f"   Oracle : {args.oracle_url}")
    print(f"   i5     : {args.i5_url}")
    print(f"   Check  : toutes les {args.check_interval}s")
    web.run_app(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()