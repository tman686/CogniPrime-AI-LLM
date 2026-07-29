"""A self-hosted reverse-proxy gateway in pure Python.

Instead of paying for (or operating) a managed nginx/ingress, run this on your
own hardware. It provides the core of a reverse proxy — longest-prefix path
routing to upstream backends, health-based backend selection, and round-robin
load balancing across replicas — with zero third-party dependencies.

The routing/load-balancing logic (:class:`RouteTable`) is pure and deterministic
so it can be unit-tested without sockets. :meth:`ReverseProxyGateway.serve`
binds an ``http.server`` and forwards requests with ``urllib`` when you actually
want to run it. For production TLS, terminate with your own certs or front it
with an OS-level listener — no SaaS required.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field


@dataclass(slots=True)
class Backend:
    """One upstream replica behind a route."""

    url: str  # e.g. "http://10.0.0.5:8080"
    healthy: bool = True


@dataclass(slots=True)
class Route:
    """A path-prefix mapped to one or more upstream backends."""

    prefix: str  # e.g. "/api/"
    backends: list[Backend] = field(default_factory=list)
    _cycle: "itertools.cycle[int] | None" = field(default=None, repr=False)

    def healthy_backends(self) -> list[Backend]:
        return [b for b in self.backends if b.healthy]


class RouteTable:
    """Longest-prefix routing with round-robin over healthy backends.

    Pure logic — no I/O. This is the piece worth testing hard; the socket layer
    on top of it is thin.
    """

    def __init__(self) -> None:
        self._routes: list[Route] = []
        self._rr: dict[str, itertools.cycle] = {}

    def add(self, prefix: str, backends: list[str]) -> Route:
        """Register a route mapping ``prefix`` to a list of backend URLs."""
        route = Route(prefix=prefix, backends=[Backend(url=u) for u in backends])
        self._routes.append(route)
        # Longest prefix first so "/api/v2/" wins over "/api/".
        self._routes.sort(key=lambda r: len(r.prefix), reverse=True)
        self._rr[prefix] = itertools.cycle(range(max(1, len(backends))))
        return route

    def match(self, path: str) -> Route | None:
        """Return the most specific route whose prefix matches ``path``."""
        for route in self._routes:
            if path.startswith(route.prefix):
                return route
        return None

    def choose_backend(self, path: str) -> Backend | None:
        """Route ``path`` and pick the next healthy backend (round-robin).

        Returns ``None`` if no route matches or every backend is unhealthy.
        """
        route = self.match(path)
        if route is None:
            return None
        healthy = route.healthy_backends()
        if not healthy:
            return None
        # Round-robin across the *healthy* subset for even distribution.
        idx = next(self._rr[route.prefix]) % len(healthy)
        return healthy[idx]

    @property
    def routes(self) -> list[Route]:
        return list(self._routes)


class ReverseProxyGateway:
    """Binds an HTTP listener and forwards to backends via :class:`RouteTable`.

    Kept intentionally thin: construction and route setup are cheap and testable;
    :meth:`serve` is the only part that touches the network.
    """

    def __init__(self, table: RouteTable | None = None) -> None:
        self.table = table or RouteTable()

    def route(self, prefix: str, backends: list[str]) -> "ReverseProxyGateway":
        """Fluently register a route; returns self for chaining."""
        self.table.add(prefix, backends)
        return self

    def resolve(self, path: str) -> str | None:
        """Return the upstream URL a request for ``path`` would be forwarded to."""
        backend = self.table.choose_backend(path)
        return backend.url if backend else None

    def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:  # pragma: no cover
        """Run the proxy. Only touches the network when actually invoked.

        Forwards method, path, headers, and body to the chosen backend using the
        standard library, then streams the response back. Run this on your own
        server; no external service is required.
        """
        import urllib.error
        import urllib.request
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        table = self.table

        class _Handler(BaseHTTPRequestHandler):
            def _proxy(self) -> None:
                backend = table.choose_backend(self.path)
                if backend is None:
                    self.send_error(502, "No healthy backend for route")
                    return
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else None
                upstream = backend.url.rstrip("/") + self.path
                req = urllib.request.Request(upstream, data=body, method=self.command)
                for key, value in self.headers.items():
                    if key.lower() not in {"host", "content-length"}:
                        req.add_header(key, value)
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        self.send_response(resp.status)
                        for key, value in resp.headers.items():
                            if key.lower() != "transfer-encoding":
                                self.send_header(key, value)
                        self.end_headers()
                        self.wfile.write(resp.read())
                except urllib.error.URLError as exc:
                    self.send_error(502, f"Upstream error: {exc}")

            # Map the common verbs onto the proxy.
            do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _proxy  # noqa: N815

        ThreadingHTTPServer((host, port), _Handler).serve_forever()
