# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Database Config class."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


class DatabaseConfig(BaseModel):
    """Model for database client relation databag.

    We need this because the mongo charm lib doesn't expose a typed data structure, so we wrap their API with this instead of passing around raw dicts.
    """

    model_config = ConfigDict(extra="ignore")

    uris: str
    username: str
    password: str


@dataclass
class TLSConfig:
    """Class representing TLS configuration received by the charm over the `tls-certificates` charm relation."""

    server_cert: str
    private_key: str
    ca_cert: str
