# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""litmus_infrastructure integration endpoint wrapper."""

import logging

import ops
import pydantic

logger = logging.getLogger()


class InfrastructureMetadata(pydantic.BaseModel):
    """User-facing data model representing the infrastructure metadata published by litmus_infrastructure providers."""

    # Note: we set extra=ignore in the model config to allow for forward compatibility in case we want to add new fields in the future without breaking existing requirers.
    model_config = pydantic.ConfigDict(extra="ignore")

    infrastructure_name: str | None = None
    model_name: str | None = None


# internal alias for clarity in the library, though they are identical
_LitmusInfraProviderAppDatabagModel = InfrastructureMetadata
"""Provider application databag model for the litmus_infrastructure interface."""


class LitmusInfrastructureProvider:
    """Wraps a litmus_infrastructure provider endpoint.

    Usage example:
        ```python
        # In your provider's charm code
        from typing import Optional
        from litmus_libs.interfaces.litmus_infrastructure import LitmusInfrastructureProvider, InfrastructureMetadata

        class LitmusInfraProviderCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_infra = LitmusInfrastructureProvider(
                    self.model.get_relation("litmus-infrastructure"),
                    self.app,
                )
                self._publish_infra_data()


            def _publish_infra_data(self):
                self._litmus_infra.publish_infrastructure_metadata(
                    InfrastructureMetadata(
                        infrastructure_name=f"{self.model.name}-{self.model.uuid}",
                        model_name=self.model.name,
                    ),
                )
        ```
    """

    def __init__(
        self,
        relations: list[ops.Relation],
        app: ops.Application,
    ):
        self._relations = relations
        self._app = app

    def publish_infrastructure_metadata(
        self,
        infrastructure_metadata: InfrastructureMetadata,
    ):
        """Publish Litmus infrastructure metadata to the ChaosCenter.

        Raises:
            pydantic.ValidationError: If the provided data does not conform to the expected schema.
        """
        try:
            infra_data = _LitmusInfraProviderAppDatabagModel(
                **infrastructure_metadata.model_dump()
            )
        except pydantic.ValidationError:
            logger.error("Attempting to publish invalid data: %s", infrastructure_metadata)
            raise

        for relation in self._relations:
            try:
                relation.save(infra_data, self._app)
            except ops.ModelError:
                logger.debug(
                    "failed to publish relation data to %s; is the relation still being created?",
                    relation,
                )


class LitmusInfrastructureRequirer:
    """Wraps a litmus_infrastructure requirer endpoint.

    Usage example:
        ```python
        # In your requirer's charm code
        from typing import Optional
        from litmus_libs.interfaces.litmus_infrastructure import LitmusInfrastructureRequirer, InfrastructureMetadata

        class LitmusInfraRequirerCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_infra = LitmusInfrastructureRequirer(
                    self.model.get_relation("litmus-infrastructure"),
                    self.app,
                )

            @property
            def _infrastructure_metadata(self) -> list[InfrastructureMetadata]:
                # Get the infrastructure metadata from the infrastructure providers
                return self._litmus_infra.get_infrastructure_metadata()

        ```
    """

    def __init__(
        self,
        relations: list[ops.Relation],
        app: ops.Application,
    ):
        self._relations = relations
        self._app = app

    def get_infrastructure_metadata(self) -> list[InfrastructureMetadata]:
        """Get the infrastructure metadata from the infrastructure providers.

        Returns:
            A list of InfrastructureMetadata objects for each provider.
        """
        infras: list[InfrastructureMetadata] = []
        for relation in sorted(self._relations, key=lambda r: r.id):
            if not relation.app or not relation.data:
                continue

            if not relation.data.get(relation.app):
                continue

            try:
                remote_data = relation.load(_LitmusInfraProviderAppDatabagModel, relation.app)
            except pydantic.ValidationError:
                logger.error("Validation failed for %s; invalid schema?", relation)
                continue

            infras.append(InfrastructureMetadata(**remote_data.model_dump()))
        return infras
