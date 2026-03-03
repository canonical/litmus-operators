import os
from pathlib import Path
from unittest.mock import call, patch

from lightkube.core.exceptions import ConfigError
from scenario import State

import kubeconfig
from conftest import (
    TEST_CLUSTER_NAME,
    TEST_SERVER_URL,
    TEST_CERT_FILE_PATH,
    TEST_NAMESPACE,
    TEST_TOKEN,
)


SAMPLE_CONFIG_PATH = (
    Path(__file__).parent / "resources" / "sample_kubeconfig"
)


@patch("kubeconfig.KubeConfig.from_service_account")
def test_kubeconfig_stored_in_the_charm(
    mock_kubeconfig,
    fake_k8s_config,
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
):
    mock_kubeconfig.return_value = fake_k8s_config

    state_out = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={
                auth_http_api_relation,
                backend_http_api_relation,
            },
            containers={nginx_container, nginx_prometheus_exporter_container},
        ),
    )

    nginx_container_out = state_out.get_container(nginx_container.name)
    kubeconfig_path = nginx_container_out.get_filesystem(ctx) / str(kubeconfig.KUBECONFIG_PATH)[1:]
    generated_config = kubeconfig_path.read_text()

    assert SAMPLE_CONFIG_PATH.read_text() == generated_config


@patch("kubeconfig.KubeConfig.from_service_account")
@patch("ops.model.Container.push")
def test_kubeconfig_not_pushed_to_the_charm_when_configerror_from_lightkube(
    mock_push,
    mock_kubeconfig,
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
):
    mock_kubeconfig.side_effect = ConfigError()

    _ = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={
                auth_http_api_relation,
                backend_http_api_relation,
            },
            containers={nginx_container, nginx_prometheus_exporter_container},
        ),
    )

    assert not any(
        mock_call.args[0] == kubeconfig.KUBECONFIG_PATH
        for mock_call in mock_push.mock_calls
    )


@patch("kubeconfig.KubeConfig.from_service_account")
@patch("ops.model.Container.push")
def test_kubeconfig_updated_when_stored_config_is_different_than_generated(
    mock_push,
    mock_kubeconfig,
    fake_k8s_config,
    ctx,
    nginx_container,
    nginx_prometheus_exporter_container,
    auth_http_api_relation,
    backend_http_api_relation,
):
    mock_kubeconfig.return_value = fake_k8s_config

    os.makedirs(
        f"{nginx_container.get_filesystem(ctx)}/.kube",
        exist_ok=True,
    )
    kubeconfig_path = nginx_container.get_filesystem(ctx) / str(kubeconfig.KUBECONFIG_PATH)[1:]
    kubeconfig_path.write_text("whatever")

    _ = ctx.run(
        ctx.on.update_status(),
        state=State(
            leader=True,
            relations={
                auth_http_api_relation,
                backend_http_api_relation,
            },
            containers={nginx_container, nginx_prometheus_exporter_container},
        ),
    )

    expected_call = call(
        kubeconfig.KUBECONFIG_PATH,
        f"api_version: {kubeconfig.KUBECONFIG_API_VERSION}\nclusters:\n- cluster:\n    certificate_auth: {TEST_CERT_FILE_PATH}\n    insecure: false\n    server: {TEST_SERVER_URL}\n  name: {TEST_CLUSTER_NAME}\ncontexts:\n- context:\n    cluster: {TEST_CLUSTER_NAME}\n    namespace: {TEST_NAMESPACE}\n    user: {TEST_CLUSTER_NAME}\n  name: {TEST_CLUSTER_NAME}\ncurrent-context: {TEST_CLUSTER_NAME}\nkind: Config\nusers:\n- name: {TEST_CLUSTER_NAME}\n  user:\n    token: {TEST_TOKEN}\n",
        make_dirs=True,
    )

    assert expected_call in mock_push.mock_calls
