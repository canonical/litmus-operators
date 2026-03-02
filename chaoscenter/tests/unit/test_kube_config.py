import yaml
from unittest.mock import patch

import pytest
from lightkube.core.exceptions import ConfigError

import kube_config
from conftest import (
    TEST_CLUSTER_NAME,
    TEST_SERVER_URL,
    TEST_CERT_FILE_PATH,
    TEST_NAMESPACE,
    TEST_TOKEN,
)


@patch("kube_config.KubeConfig.from_service_account")
def test_generate_kubeconfig_renders_correct_config(
    mock_kubeconfig, fake_k8s_config
):
    mock_kubeconfig.return_value = fake_k8s_config

    output = kube_config.generate_kubeconfig()
    kubeconfig = yaml.safe_load(output)

    assert kubeconfig["api_version"] == kube_config.KUBECONFIG_API_VERSION
    assert kubeconfig["kind"] == kube_config.KUBECONFIG_KIND
    assert kubeconfig["current-context"] == TEST_CLUSTER_NAME

    assert kubeconfig["clusters"][0]["name"] == TEST_CLUSTER_NAME
    assert kubeconfig["clusters"][0]["cluster"]["server"] == TEST_SERVER_URL
    assert kubeconfig["clusters"][0]["cluster"]["certificate_auth"] == TEST_CERT_FILE_PATH

    assert kubeconfig["contexts"][0]["name"] == TEST_CLUSTER_NAME
    assert kubeconfig["contexts"][0]["context"]["namespace"] == TEST_NAMESPACE

    assert kubeconfig["users"][0]["name"] == TEST_CLUSTER_NAME
    assert kubeconfig["users"][0]["user"]["token"] == TEST_TOKEN


@patch("kube_config.KubeConfig.from_service_account")
def test_generate_kubeconfig_raises_when_configerror(mock_kubeconfig):
    mock_kubeconfig.side_effect = ConfigError()

    with pytest.raises(kube_config.KubernetesConfigError):
        kube_config.generate_kubeconfig()


@patch("kube_config.KubeConfig.from_service_account")
def test_generate_kubeconfig_raises_when_no_current_context(mock_kubeconfig, fake_k8s_config):
    fake_k8s_config.current_context = None
    mock_kubeconfig.return_value = fake_k8s_config

    with pytest.raises(kube_config.KubernetesConfigError):
        kube_config.generate_kubeconfig()


def test_remove_none_removes_none_from_dict():
    test_dict = {
        "this": 1,
        "is": None,
        "just": {"a": None, "test": 2},
    }

    cleaned = kube_config.remove_none(test_dict)

    assert cleaned == {
        "this": 1,
        "just": {"test": 2},
    }


def test_remove_none_removes_none_from_list():
    test_list = [1, None, {"try": None, "me": 2}, [None, 3]]

    cleaned = kube_config.remove_none(test_list)

    assert cleaned == [1, {"me": 2}, [3]]
