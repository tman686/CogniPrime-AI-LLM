"""Self-hostable infrastructure — no paid dependencies.

Everything here runs on hardware you own (a RAID box, a home server, a
self-built cloud) using only the Python standard library and open-source
components. The gateway replaces a paid/managed reverse proxy with a small
pure-stdlib one you can run yourself.
"""

from omegax.infra.gateway import Backend, ReverseProxyGateway, Route, RouteTable

__all__ = ["Backend", "ReverseProxyGateway", "Route", "RouteTable"]
