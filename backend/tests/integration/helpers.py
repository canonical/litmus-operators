# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

from jubilant import Juju


def get_unit_ip_address(juju: Juju, app_name: str, unit_no: int):
    """Return a juju unit's IP address."""
    return juju.status().apps[app_name].units[f"{app_name}/{unit_no}"].address
