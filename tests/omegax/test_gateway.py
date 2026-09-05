"""Tests for the self-hosted reverse-proxy gateway routing logic."""

from __future__ import annotations

from omegax.infra.gateway import ReverseProxyGateway, RouteTable


def test_longest_prefix_wins() -> None:
    table = RouteTable()
    table.add("/api/", ["http://api:8000"])
    table.add("/api/v2/", ["http://apiv2:8000"])

    assert table.match("/api/v2/users").prefix == "/api/v2/"
    assert table.match("/api/users").prefix == "/api/"
    assert table.match("/static/logo.png") is None


def test_round_robin_across_healthy_backends() -> None:
    table = RouteTable()
    table.add("/app/", ["http://a:80", "http://b:80", "http://c:80"])
    chosen = [table.choose_backend("/app/x").url for _ in range(6)]
    # Even distribution across the three replicas.
    assert chosen.count("http://a:80") == 2
    assert chosen.count("http://b:80") == 2
    assert chosen.count("http://c:80") == 2


def test_unhealthy_backends_are_skipped() -> None:
    table = RouteTable()
    route = table.add("/app/", ["http://a:80", "http://b:80"])
    route.backends[0].healthy = False
    chosen = {table.choose_backend("/app/x").url for _ in range(4)}
    assert chosen == {"http://b:80"}


def test_no_route_returns_none() -> None:
    table = RouteTable()
    table.add("/api/", ["http://a:80"])
    assert table.choose_backend("/nope") is None


def test_gateway_resolve_end_to_end() -> None:
    gw = ReverseProxyGateway().route("/api/", ["http://api:9000"]).route(
        "/", ["http://web:3000"]
    )
    assert gw.resolve("/api/health") == "http://api:9000"
    assert gw.resolve("/index.html") == "http://web:3000"
