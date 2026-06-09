"""Host domain model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from oe_lifecycle_manager.domain.common import OeVersion


@dataclass
class InventorySnapshot:
    """Collected host inventory data."""

    snapshot_id: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Host:
    """Managed host."""

    host_id: str
    hostname: str
    current_version: OeVersion
    inventory: InventorySnapshot | None = None
