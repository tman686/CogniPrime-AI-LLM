"""Run CogniPrime's own reverse proxy — no nginx, no paid load balancer.

Point one public port at your self-hosted services. This is the pure-Python
gateway from ``omegax.infra.gateway``; it does longest-prefix routing and
round-robin load balancing across replicas on hardware you own.

    python deploy/gateway_example.py

For TLS, run behind your own certs (e.g. terminate with your OS/router) — you
still don't need a paid proxy.
"""

from __future__ import annotations

from omegax.infra.gateway import ReverseProxyGateway


def build_gateway() -> ReverseProxyGateway:
    return (
        ReverseProxyGateway()
        # API replicas (scale by adding more URLs to the list).
        .route("/api/", ["http://127.0.0.1:8001", "http://127.0.0.1:8002"])
        # Vector DB and graph DB dashboards, if you expose them internally.
        .route("/qdrant/", ["http://127.0.0.1:6333"])
        .route("/graph/", ["http://127.0.0.1:7474"])
        # Everything else → the web/dashboard app.
        .route("/", ["http://127.0.0.1:3000"])
    )


if __name__ == "__main__":
    build_gateway().serve(host="0.0.0.0", port=8080)
