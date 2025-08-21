# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Utilities to work with litmus."""

import importlib

__all__ = [
    "DatabaseConfig"
]

current_package = __package__


class _LazyModule:
    def __init__(self, module_name: str):
        self.module_name = module_name
        self.module = None

    def _load(self):
        if self.module is None:
            self.module = importlib.import_module(self.module_name, current_package)
        return self.module

    def __getattr__(self, item: str):
        module = self._load()
        return getattr(module, item)


# Create lazy-loaded modules
DatabaseConfig = _LazyModule(".models")
