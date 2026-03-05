# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""litmus_infrastructure integration endpoint wrapper."""

import logging
from dataclasses import asdict, dataclass

import ops
import pydantic

logger = logging.getLogger()


@dataclass
class InfrastructureDatabagModel:
    """User-facing data model representing the infrastructure data published by litmus_infrastructure providers."""

    infrastructure_name: str
    model_name: str


class _LitmusInfraProviderAppDatabagModel(pydantic.BaseModel):
    """Provider application databag model for the litmus_infrastructure interface."""

    infrastructure_name: str | None = None
    model_name: str | None = None


class LitmusInfrastructureProvider:
    """Wraps a litmus_infrastructure provider endpoint.

    Usage example:
        ```python
        # In your provider's charm code
        from typing import Optional
        from litmus_libs.interfaces.litmus_infrastructure import LitmusInfrastructureProvider, InfrastructureDatabagModel

        class LitmusInfraProviderCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_infra = LitmusInfrastructureProvider(
                    self.model.relations["litmus-infrastructure"],
                    self.app,
                    self.unit,
                )
                self._publish_infra_data()


            def _publish_infra_data(self):
                self._litmus_infra.publish_data(
                    InfrastructureDatabagModel(
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
        unit: ops.Unit,
    ):
        self._relations = relations
        self._app = app
        self._unit = unit

    def publish_data(
        self,
        data: InfrastructureDatabagModel,
    ):
        """Publish Litmus infrastructure data to the ChaosCenter.

        Raises:
            pydantic.ValidationError: If the provided data does not conform to the expected schema.
        """
        try:
            infra_data = _LitmusInfraProviderAppDatabagModel(**asdict(data))
        except pydantic.ValidationError:
            logger.error("Attempting to publish invalid data: %s", data)
            raise

        if not self._unit.is_leader():
            raise RuntimeError("Only the leader unit can publish to the app databag")

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
        from litmus_libs.interfaces.litmus_infrastructure import LitmusInfrastructureRequirer, InfrastructureDatabagModel

        class LitmusInfraRequirerCharm(CharmBase):
            def __init__(self, *args):
                super().__init__(*args)
                self._litmus_infra = LitmusInfrastructureRequirer(
                    self.model.relations["litmus-infrastructure"],
                    self.app,
                )

            @property
            def _infrastructure_data(self) -> list[InfrastructureDatabagModel]:
                # Get the infrastructure data from all the infrastructure providers
                return self._litmus_infra.get_all_data()

        ```
    """

    def __init__(
        self,
        relations: list[ops.Relation],
        app: ops.Application,
    ):
        self._relations = relations
        self._app = app

    def get_data(self, relation_id: int) -> InfrastructureDatabagModel | None:
        """Get the infrastructure data from a specific relation.

        Args:
            relation_id: The relation ID to get the data from.

        Returns:
            An InfrastructureDatabagModel object for the specified relation, or None if not found.

        """
        relation = next((r for r in self._relations if r.id == relation_id), None)
        if not relation:
            logger.error("Relation with ID %s not found", relation_id)
            return None

        if not (relation.app and relation.data and relation.data.get(relation.app)):
            return None

        try:
            remote_data = relation.load(_LitmusInfraProviderAppDatabagModel, relation.app)
        except pydantic.ValidationError:
            logger.error("Validation failed for %s; invalid schema?", relation)
            return None

        # Can happen during upgrades if the provider writes a newer databag schema
        # that this requirer version does not yet understand.
        if not remote_data.infrastructure_name or not remote_data.model_name:
            logger.warning(
                "Incompatible or incomplete databag schema (possibly due to an ongoing upgrade)."
            )
            return None

        return InfrastructureDatabagModel(**remote_data.model_dump())

    def get_all_data(self) -> list[InfrastructureDatabagModel]:
        """Get the infrastructure data from all the relations.

        Returns:
            A list of InfrastructureDatabagModel objects for each relation.
        """
        infras: list[InfrastructureDatabagModel] = []
        for relation in sorted(self._relations, key=lambda r: r.id):
            relation_data = self.get_data(relation.id)
            if relation_data:
                infras.append(relation_data)
        return infras
