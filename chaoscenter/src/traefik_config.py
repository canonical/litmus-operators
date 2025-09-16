from collections import namedtuple
import socket
from typing import Dict, Sequence


EntryPoint = namedtuple("Port", "name, port")


def entrypoints() -> Sequence[EntryPoint]:
    return (EntryPoint("litmus-chaoscenter", 8185),)


def static_ingress_config() -> dict:
    entry_points = {}
    for name, port in entrypoints():
        entry_points[name] = {"address": f":{port}"}

    return {"entryPoints": entry_points}


def _build_lb_server_config(scheme: str, port: int) -> Dict[str, str]:
    """Build the server portion of the loadbalancer config of Traefik ingress."""
    return {"url": f"{scheme}://{socket.getfqdn()}:{port}"}


def ingress_config(model_name: str, app_name: str, tls: bool) -> dict:
    """Build a raw ingress configuration for Traefik."""
    http_routers = {}
    http_services = {}
    for name, port in entrypoints():
        http_routers[f"juju-{model_name}-{app_name}-{name}"] = {
            "entryPoints": [name],
            "service": f"juju-{model_name}-{app_name}-service-{name}",
            "rule": "ClientIP(`0.0.0.0/0`)",
            # TODO do we need middlewares?
        }
        # ref https://doc.traefik.io/traefik/v2.0/user-guides/grpc/#with-https
        http_services[f"juju-{model_name}-{app_name}-service-{name}"] = {
            "loadBalancer": {
                "servers": [
                    _build_lb_server_config("https" if tls else "http", port)
                ]
            }
        }
    return {
        "http": {
            "routers": http_routers,
            "services": http_services,
        },
    }
