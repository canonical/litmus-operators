# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Shared abstractions for litmus interfaces."""

import logging
from typing import Any, Dict, Optional, Type, TypeVar

import ops
import pydantic

logger = logging.getLogger()


class VersionMismatchError(Exception):
    """Raised if the schema version in the relation data is not the one supported by this library version."""


class BaseVersionedModel(pydantic.BaseModel):
    """Base class of all our internal models.

    This class is intended to be inherited by all databag models
    so they share a standardized version field to make it easier
    to implement version negotiation.
    """

    version: int


_M = TypeVar("_M", bound=BaseVersionedModel)


def _get_versioned_databag(relation: ops.Relation, model: Type[_M]) -> Optional[_M]:
    """Attempt to load a relation databag containing a version schema."""
    try:
        version = relation.load(
            BaseVersionedModel,
            relation.app,
        ).version
    except pydantic.ValidationError:
        logger.debug(
            "Validation failed for %s; is the relation still bootstrapping?", str(relation)
        )
        return None

    # hacky way to get the version value from the model class
    model_version = model.model_fields["version"].default
    if version != model_version:
        raise VersionMismatchError(
            f"schema {relation.name}@v{version} is not the version supported by this library ({relation.name}@v{model_version})"
        )

    try:
        return relation.load(
            model,
            relation.app,
        )
    except pydantic.ValidationError:
        # this is a worse situation: we've declared vX, but validation using the vX schema is failing.
        logger.error("Validation failed for %s; invalid version (%s) schema?", relation, version)

    return None


def _set_versioned_databag(
    relation: ops.Relation,
    owner: ops.Application | ops.Unit,
    model: Type[pydantic.BaseModel],
    data: Dict[str, Any],
):
    """Attempt to write a relation databag using a versioned schema.

    Will raise if the data is invalid, or silently pass if a write fails because of a model error.
    """
    try:
        model_instance = model(**data)
    except pydantic.ValidationError:
        logger.error("Attempting to publish invalid data: %s", data)
        raise

    try:
        relation.save(
            model_instance,
            owner,
        )
    except ops.ModelError:
        logger.debug("failed to publish relation data; is the relation still being created?")


class SimpleEndpointWrapper:
    """Endpoint wrapper base class."""

    def __init__(
        self,
        relation: Optional[ops.Relation],
        app: ops.Application,
    ):
        self._relation = relation
        self._app = app

    def _set(self, model: Type[BaseVersionedModel], data: Dict[str, Any]):
        if not self._relation:
            return
        _set_versioned_databag(relation=self._relation, owner=self._app, model=model, data=data)

    def _get(self, model: Type[_M]) -> Optional[_M]:
        if not self._relation:
            return None
        datamodel = _get_versioned_databag(relation=self._relation, model=model)
        return datamodel
