import json
from scenario import State, Relation
import pytest

from urllib.parse import urlparse

from coordinated_workers.nginx import NGINX_CONFIG
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
            f"server {auth_endpoint_parsed.netloc}:{auth_endpoint_parsed.port}"
            in config
        )
    else:
        if auth_endpoint_parsed.scheme == "http":
            assert f"server {auth_endpoint_parsed.netloc}:80" in config
        else:
            assert f"server {auth_endpoint_parsed.netloc}:443" in config

    if backend_endpoint_parsed.port:
        assert (
            f"server {backend_endpoint_parsed.netloc}:{backend_endpoint_parsed.port}"
            in config
        )
    else:
        if backend_endpoint_parsed.scheme == "http":
            assert f"server {backend_endpoint_parsed.netloc}:80" in config
        else:
            assert f"server {backend_endpoint_parsed.netloc}:443" in config



def test_calling_config_with_missing_hostname_raises():
    with pytest.raises(ValueError):
        nginx_config.get_config(None, "http://foo.bar:80", "http://foo.bar:3030")

def test_calling_config_with_missing_auth_url_raises():
    with pytest.raises(ValueError):
        nginx_config.get_config("foo.bar", None, "http://foo.bar:3030")

def test_calling_config_with_missing_backend_url_raises():
    with pytest.raises(ValueError):
        nginx_config.get_config("foo.bar", "http://foo.bar:80", None)