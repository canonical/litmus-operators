# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
from contextlib import contextmanager
import json
import pathlib
from unittest.mock import patch

from ops.testing import Container, Context
import pytest
from scenario import Relation
from certificates_helpers import mock_cert_and_key
from coordinated_workers.nginx import CA_CERT_PATH
from charm import LitmusChaoscenterCharm
from ops.testing import Exec


@pytest.fixture(scope="session")
def unit_fqdn():
    yield "app-0.app-headless.default.svc.cluster.local"


@pytest.fixture
def chaoscenter_charm(unit_fqdn):
    with patch(
        "socket.getfqdn",
        return_value=unit_fqdn,
    ):
        yield LitmusChaoscenterCharm


@pytest.fixture
def nginx_container():
    return Container(
        "chaoscenter",
        can_connect=True,
        execs=[Exec(["update-ca-certificates", "--fresh"], return_code=0)],
    )


@pytest.fixture
def nginx_prometheus_exporter_container():
    return Container(
        "nginx-prometheus-exporter",
        can_connect=True,
    )


@pytest.fixture
def ctx(chaoscenter_charm):
    return Context(charm_type=chaoscenter_charm)


@contextmanager
def patch_cert_and_key_ctx(tls: bool):
    with patch(
        "charms.tls_certificates_interface.v4.tls_certificates.TLSCertificatesRequiresV4.get_assigned_certificate",
        return_value=mock_cert_and_key() if tls else (None, None),
    ):
        yield


@pytest.fixture()
def patch_cert_and_key():
    with patch_cert_and_key_ctx(True):
        yield


@pytest.fixture()
def patch_write_to_ca_path():
    pathlib_write_text = pathlib.Path.write_text

    def selective_write_to_ca_path(path, content, *args, **kwargs):
        if path == pathlib.Path(CA_CERT_PATH):
            return None
        else:
            return pathlib_write_text(path, content, *args, **kwargs)

    with patch(
        "coordinated_workers.nginx.Path.write_text",
        new=selective_write_to_ca_path,
    ):
        yield


@pytest.fixture
def auth_http_api_relation():
    return Relation(
        "auth-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("http://foo.bar:3000"),
        },
    )


@pytest.fixture
def backend_http_api_relation():
    return Relation(
        "backend-http-api",
        remote_app_data={
            "version": json.dumps(0),
            "endpoint": json.dumps("http://foo.bar:8080"),
        },
    )


@pytest.fixture
def tls_certificates_relation():
    return Relation("tls-certificates")


@pytest.fixture
def ingress_relation():
    return Relation(
        "ingress", remote_app_data={"external_host": "1.2.3.4", "scheme": "http"}
    )


@pytest.fixture
def ingress_over_https_relation():
    return Relation(
        "ingress", remote_app_data={"external_host": "1.2.3.4", "scheme": "https"}
    )


@pytest.fixture
def workload_tracing_relation():
    return Relation(
        "workload-tracing",
        remote_app_data={
            "receivers": json.dumps(
                [
                    {
                        "protocol": {"name": "otlp_grpc", "type": "grpc"},
                        "url": "foo.bar:4317",
                    }
                ]
            )
        },
    )
