"""Lifecycle domain model."""

from dataclasses import dataclass, field

from oe_lifecycle_manager.domain.common import OeVersion


@dataclass(frozen=True)
class LifecyclePolicy:
    """Lifecycle policy for an openEuler release."""

    version: OeVersion
    support_status: str


@dataclass
class UpgradePath:
    """Supported source-to-target upgrade path."""

    source: OeVersion
    target: OeVersion
    supported: bool = True
    rules: list[str] = field(default_factory=list)
