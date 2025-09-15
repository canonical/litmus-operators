#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper methods for creating Nginx configuration for Litmus."""

import logging
from typing import Dict, List, Optional, Set

from coordinated_workers.nginx import (
    CERT_PATH,
    KEY_PATH,
    NginxUpstream,
    NginxLocationConfig,
    NginxConfig,
)

from urllib.parse import urlparse, ParseResult


logger = logging.getLogger(__name__)

http_server_port = 8185


def get_config(
    hostname: str,
    auth_url: Optional[str],
    backend_url: Optional[str],
    tls_available: bool = False,
) -> str:
    if not hostname or not auth_url or not backend_url:
        raise ValueError(
            f"get_config was called with invalid arguments: {hostname=} {auth_url=} {backend_url=}"
        )
    auth_parsed_url = urlparse(auth_url)
    backend_parsed_url = urlparse(backend_url)
    # TODO how about we check the port and if it's not there, deduce the port from the scheme
    auth_scheme = _get_scheme_from_url(auth_parsed_url)
    auth_port = _get_port_from_url(auth_parsed_url)
    backend_scheme = _get_scheme_from_url(backend_parsed_url)
    backend_port = _get_port_from_url(backend_parsed_url)

    config = NginxConfig(
        server_name=hostname,
        upstream_configs=_upstreams(auth_port, backend_port),
        server_ports_to_locations=_server_ports_to_locations(
            auth_scheme=auth_scheme,
            backend_scheme=backend_scheme,
        ),
        enable_status_page=False,
    )
    return config.get_config(
        _upstreams_to_addresses(auth_parsed_url.hostname, backend_parsed_url.hostname),  # type: ignore[arg-type]
        listen_tls=tls_available,
        root_path="/dist",
    )


def _get_scheme_from_url(url: ParseResult) -> str:
    if url.scheme:
        return url.scheme
    return "http"


def _get_port_from_url(url: ParseResult) -> int:
    if url.port:
        return url.port
    if url.scheme == "http":
        return 80
    return 443


def _server_ports_to_locations(
    auth_scheme: str,
    backend_scheme: str,
) -> Dict[int, List[NginxLocationConfig]]:
    """Generate a mapping from server ports to a list of Nginx location configurations."""

    return {
        http_server_port: _generate_http_locations(auth_scheme, backend_scheme),
    }


def _generate_http_locations(
    auth_scheme: str, backend_scheme: str
) -> List[NginxLocationConfig]:
    return [
        NginxLocationConfig(
            path="/auth",
            backend="auth",
            rewrite=["^/auth(/.*)$", "$1", "break"],
            upstream_tls=True if auth_scheme == "https" else False,
            extra_directives=_extra_directives(auth_scheme),
        ),
        NginxLocationConfig(
            path="/api",
            backend="backend",
            upstream_tls=True if backend_scheme == "https" else False,
            extra_directives=_extra_directives(backend_scheme),
        ),
    ]


def _extra_directives(scheme: str) -> Dict[str, List[str]]:
    if scheme == "https":
        return {
            "proxy_ssl_verify": ["off"],
            "proxy_ssl_session_reuse": ["on"],
            "proxy_ssl_certificate": [CERT_PATH],
            "proxy_ssl_certificate_key": [KEY_PATH],
        }
    return {}


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
