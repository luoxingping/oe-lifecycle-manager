"""Rollback domain model."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RollbackType(str, Enum):
    """Supported rollback point types."""

    LVM = "lvm"
    KERNEL = "kernel"
    RPM = "rpm"


@dataclass
class RollbackPoint:
    """Rollback point descriptor."""

    point_id: str
    task_id: str
    rollback_type: RollbackType
    status: str
    payload: dict[str, Any] = field(default_factory=dict)
