import base64
from unittest.mock import patch

from conftest import (
    TEST_CLUSTER_NAME,
    TEST_SERVER_URL,
    TEST_NAMESPACE,
    TEST_CA_CERT_CONTENT,
    TEST_TOKEN,
)

import kube_config


def test_get_cluster_name(fake_k8s_config):
    name = kube_config._get_cluster_name(fake_k8s_config)
    assert name == TEST_CLUSTER_NAME


def test_get_server_url(fake_k8s_config):
    url = kube_config._get_server_url(fake_k8s_config)
    assert url == TEST_SERVER_URL


def test_get_namespace(fake_k8s_config):
    namespace = kube_config._get_namespace(fake_k8s_config)
    assert namespace == TEST_NAMESPACE


def test_get_ca_data(fake_k8s_config):
    result = kube_config._get_ca_data(fake_k8s_config)
    expected = base64.b64encode(TEST_CA_CERT_CONTENT).decode()
    assert result == expected


def test_get_user_token(fake_k8s_config):
    token = kube_config._get_user_token(fake_k8s_config)
    assert token == TEST_TOKEN


@patch("kube_config.Environment")
@patch("kube_config.KubeConfig")
def test_generate_kubeconfig_file_renders_template(
    mock_kubeconfig, mock_jinja_env, fake_k8s_config
):
    mock_kubeconfig.from_service_account.return_value = fake_k8s_config
    mock_template = mock_jinja_env.return_value.get_template.return_value

    kube_config.generate_kubeconfig()

    mock_template.render.assert_called_once_with(
        cluster_name=TEST_CLUSTER_NAME,
        server_url=TEST_SERVER_URL,
        namespace=TEST_NAMESPACE,
        ca_data=base64.b64encode(TEST_CA_CERT_CONTENT).decode(),
        user_token=TEST_TOKEN,
    )
