#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods for creating Nginx configuration for Litmus."""

import logging
from typing import Dict, List, Set

from coordinated_workers.nginx import NginxUpstream, NginxLocationConfig, NginxConfig

from urllib.parse import urlparse, ParseResult


logger = logging.getLogger(__name__)


http_locations: List[NginxLocationConfig] = [
    NginxLocationConfig(path="/auth", backend="auth"),
    NginxLocationConfig(path="/api", backend="backend"),
]

http_server_port = 8185


def get_config(hostname: str, auth_url: str, backend_url: str) -> NginxConfig:
    if not hostname or not auth_url or not backend_url:
        raise ValueError(
            f"get_config was called with invalid arguments: {hostname=} {auth_url=} {backend_url=}"
        )
    auth_parsed_url = urlparse(auth_url)
    backend_parsed_url = urlparse(backend_url)
    # TODO how about we check the port and if it's not there, deduce the port from the scheme
    auth_port = _get_port_from_url(auth_parsed_url)
    backend_port = _get_port_from_url(backend_parsed_url)

    config = NginxConfig(
        server_name=hostname,
        upstream_configs=_upstreams(auth_port, backend_port),
        server_ports_to_locations=_server_ports_to_locations(
            tls_available=False,
        ),
        enable_status_page=False,
    )
    return config.get_config(
        _upstreams_to_addresses(auth_parsed_url.netloc, backend_parsed_url.netloc),
        listen_tls=False,
        root_path="/dist",
    )


def _get_port_from_url(url: ParseResult) -> int:
    if url.port:
        return url.port
    if url.scheme == "http":
        return 80
    return 443


def _server_ports_to_locations(
    tls_available: bool,
) -> Dict[int, List[NginxLocationConfig]]:
    """Generate a mapping from server ports to a list of Nginx location configurations."""

    return {
        http_server_port: http_locations,
    }


def _upstreams_to_addresses(auth_url: str, backend_url: str) -> Dict[str, Set[str]]:
    """Generate a list of addresses that serve the provided upstreams."""

    return {
        "auth": {auth_url},
        "backend": {backend_url},
    }


def _upstreams(auth_port: int, backend_port: int) -> List[NginxUpstream]:
    """Generate the list of Nginx upstream metadata configurations."""
    return [
        NginxUpstream("auth", auth_port, "auth"),
        NginxUpstream("backend", backend_port, "backend"),
    ]
