from tests.integration.helpers import deploy_cluster


def test_deployment(juju):
    """Verify that we can deploy and integrate the cluster, without waiting for it to go to active."""
    deploy_cluster(juju, wait_for_active=True)
