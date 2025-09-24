# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.
import json
import pathlib
from unittest.mock import patch

from ops.testing import Container, Context
import pytest
from scenario import Relation
from certificates_helpers import mock_cert_and_key
from coordinated_workers.nginx import CA_CERT_PATH
from charm import LitmusChaoscenterCharm


@pytest.fixture
def chaoscenter_charm():
    with patch(
        "socket.getfqdn",
        return_value="app-0.app-headless.default.svc.cluster.local",
    ):
        yield LitmusChaoscenterCharm


@pytest.fixture
def nginx_container():
    return Container(
        "chaoscenter",
        can_connect=True,
    )


@pytest.fixture
def ctx(chaoscenter_charm):
    return Context(charm_type=chaoscenter_charm)


@pytest.fixture
def cert_and_key():
    return mock_cert_and_key()


@pytest.fixture()
def patch_cert_and_key(cert_and_key):
    with patch(
        "charms.tls_certificates_interface.v4.tls_certificates.TLSCertificatesRequiresV4.get_assigned_certificate",
        return_value=cert_and_key,
    ):
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
