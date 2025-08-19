# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Database Config class."""

import dataclasses
from typing import Optional


@dataclasses.dataclass(init=False)
class DatabaseConfig:
    """Model for database client relation databag."""

    database: Optional[str]
    replset: Optional[str]
    uris: Optional[str]
    username: Optional[str]
    password: Optional[str]

    def __init__(self, **kwargs):
        names = set([f.name for f in dataclasses.fields(self)])
        for k, v in kwargs.items():
            # hack to ignore extra fields that are not defined in this dataclass
            if k in names:
                setattr(self, k, v)
