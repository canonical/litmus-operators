import json
from pathlib import Path

from scenario import State, Relation
import pytest

from urllib.parse import urlparse

from coordinated_workers.nginx import CERT_PATH, KEY_PATH, NGINX_CONFIG
import nginx_config


@pytest.mark.parametrize(
    "auth_endpoint",
    (
        "http://foo.bar:8185",
        "https://secure.foo.bar:8174",
        "http://10.10.22.44",
        "https://127.0.0.1:8080",
    ),
)
@pytest.mark.parametrize(
    "backend_endpoint",
    (
        "http://foo.bar:9200",
        "https://secure.foo.bar:8443",
        "http://10.10.22.44:4043",
        "https://127.0.0.1",
    ),
)
def test_config_contains_correct_urls(
    ctx, nginx_container, auth_endpoint, backend_endpoint
):
    # GIVEN chaoscenter related to backend and auth
    auth_relation = Relation(
        "auth-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps(auth_endpoint),
        },
    )

    backend_relation = Relation(
        "backend-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps(backend_endpoint),
        },
    )

    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={auth_relation, backend_relation},
            containers={nginx_container},
        ),
    )

    # WHEN we peek into the generated nginx config
    nginx_container_out = state_out.get_container(nginx_container.name)
    nginx_config_path = nginx_container_out.get_filesystem(ctx) / NGINX_CONFIG[1:]

    config = nginx_config_path.read_text()

    # THEN it contains the server section with the correct host and port
    auth_endpoint_parsed = urlparse(auth_endpoint)
    backend_endpoint_parsed = urlparse(backend_endpoint)

    if auth_endpoint_parsed.port:
        assert (
            f"server {auth_endpoint_parsed.hostname}:{auth_endpoint_parsed.port}"
            in config
        )
    else:
        if auth_endpoint_parsed.scheme == "http":
            assert f"server {auth_endpoint_parsed.hostname}:80" in config
        else:
            assert f"server {auth_endpoint_parsed.hostname}:443" in config

    if backend_endpoint_parsed.port:
        assert (
            f"server {backend_endpoint_parsed.hostname}:{backend_endpoint_parsed.port}"
            in config
        )
    else:
        if backend_endpoint_parsed.scheme == "http":
            assert f"server {backend_endpoint_parsed.hostname}:80" in config
        else:
            assert f"server {backend_endpoint_parsed.hostname}:443" in config


def test_config_contains_auth_rewrite(ctx, nginx_container):
    # GIVEN chaoscenter related to backend and auth
    auth_relation = Relation(
        "auth-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("http://foo.bar:3000"),
        },
    )

    backend_relation = Relation(
        "backend-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("http://foo.bar:8000"),
        },
    )

    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={auth_relation, backend_relation},
            containers={nginx_container},
        ),
    )

    # WHEN we peek into the generated nginx config
    nginx_container_out = state_out.get_container(nginx_container.name)
    nginx_config_path = nginx_container_out.get_filesystem(ctx) / NGINX_CONFIG[1:]

    config = nginx_config_path.read_text()

    # THEN it contains the server section with the correct host and port
    assert "rewrite '^/auth(/.*)$' $1 break;" in config


def test_calling_config_with_missing_hostname_raises():
    with pytest.raises(ValueError):
        nginx_config.get_config(None, "http://foo.bar:80", "http://foo.bar:3030")


def test_calling_config_with_missing_auth_url_raises():
    with pytest.raises(ValueError):
        nginx_config.get_config("foo.bar", None, "http://foo.bar:3030")


def test_calling_config_with_missing_backend_url_raises():
    with pytest.raises(ValueError):
        nginx_config.get_config("foo.bar", "http://foo.bar:80", None)


def test_config_contains_ssl_config_when_tls_relation_created(
    ctx,
    nginx_container,
    auth_http_api_relation,
    backend_http_api_relation,
    tls_certificates_relation,
    patch_cert_and_key,
    patch_write_to_ca_path,
):
    # GIVEN chaoscenter related to backend and auth
    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={
                auth_http_api_relation,
                backend_http_api_relation,
                tls_certificates_relation,
            },
            containers={nginx_container},
        ),
    )

    # WHEN we peek into the generated nginx config
    nginx_container_out = state_out.get_container(nginx_container.name)
    nginx_config_path = nginx_container_out.get_filesystem(ctx) / NGINX_CONFIG[1:]

    config = nginx_config_path.read_text()

    # THEN it contains SSL configuration
    assert "listen 8185 ssl;" in config
    assert "listen [::]:8185 ssl;" in config
    assert f"ssl_certificate {CERT_PATH};" in config
    assert f"ssl_certificate_key {KEY_PATH};" in config


@pytest.mark.parametrize(
    "auth_endpoint, backend_endpoint, expected_location_config",
    (
        (
            "http://ssl.disabled.auth:3000",
            "http://ssl.disabled.backend:8080",
            ["set $backend http://auth;", "set $backend http://backend;"],
        ),
        (
            "https://ssl.enabled.auth:3001",
            "https://ssl.disabled.backend:8081",
            ["set $backend https://auth;", "set $backend https://backend;"],
        ),
        (
            "http://ssl.disabled.auth:3000",
            "https://ssl.disabled.backend:8081",
            ["set $backend http://auth;", "set $backend https://backend;"],
        ),
        (
            "https://ssl.enabled.auth:3001",
            "http://ssl.disabled.auth:8080",
            ["set $backend https://auth;", "set $backend http://backend;"],
        ),
    ),
)
def test_config_contains_correct_locations_config_depending_on_endpoints_configuration(
    ctx,
    nginx_container,
    tls_certificates_relation,
    patch_cert_and_key,
    patch_write_to_ca_path,
    auth_endpoint,
    backend_endpoint,
    expected_location_config,
):
    # GIVEN chaoscenter related to backend and auth
    auth_relation = Relation(
        "auth-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps(auth_endpoint),
        },
    )

    backend_relation = Relation(
        "backend-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps(backend_endpoint),
        },
    )

    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={
                auth_relation,
                backend_relation,
                tls_certificates_relation,
            },
            containers={nginx_container},
        ),
    )

    # WHEN we peek into the generated nginx config
    nginx_container_out = state_out.get_container(nginx_container.name)
    nginx_config_path = nginx_container_out.get_filesystem(ctx) / NGINX_CONFIG[1:]

    config = nginx_config_path.read_text()

    # THEN it contains SSL configuration
    for location in expected_location_config:
        assert location in config


def test_generated_ssl_config_matches_expected_config(
    ctx,
    nginx_container,
    tls_certificates_relation,
    patch_cert_and_key,
    patch_write_to_ca_path,
):
    # GIVEN chaoscenter related to backend and auth
    auth_relation = Relation(
        "auth-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("https://auth:3001"),
        },
    )

    backend_relation = Relation(
        "backend-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("https://backend:8081"),
        },
    )
    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={
                auth_relation,
                backend_relation,
                tls_certificates_relation,
            },
            containers={nginx_container},
        ),
    )

    # WHEN we peek into the generated nginx config
    nginx_container_out = state_out.get_container(nginx_container.name)
    nginx_config_path = nginx_container_out.get_filesystem(ctx) / NGINX_CONFIG[1:]
    generated_config = nginx_config_path.read_text()

    # THEN the config contains the expected directives
    sample_config_path = (
        Path(__file__).parent / "resources" / "sample_nginx_litmus_ssl.conf"
    )
    assert sample_config_path.read_text() == generated_config
