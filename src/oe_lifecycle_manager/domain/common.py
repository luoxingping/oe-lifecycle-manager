"""Shared domain primitives."""

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    """Supported risk levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskStatus(str, Enum):
    """Upgrade task state."""

    CREATED = "CREATED"
    INVENTORY_COLLECTING = "INVENTORY_COLLECTING"
    PRECHECK_RUNNING = "PRECHECK_RUNNING"
    RISK_ANALYZING = "RISK_ANALYZING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    ROLLBACK_POINT_CREATING = "ROLLBACK_POINT_CREATING"
    UPGRADING = "UPGRADING"
    REBOOT_REQUIRED = "REBOOT_REQUIRED"
    POSTCHECK_RUNNING = "POSTCHECK_RUNNING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    RESUMABLE = "RESUMABLE"
    ROLLBACKING = "ROLLBACKING"
    ROLLED_BACK = "ROLLED_BACK"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Workflow step state."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class OeVersion:
    """openEuler version value object."""

    value: str
