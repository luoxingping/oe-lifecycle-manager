"""Upgrade domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from oe_lifecycle_manager.domain.common import OeVersion, StepStatus, TaskStatus
from oe_lifecycle_manager.domain.lifecycle import UpgradePath


@dataclass
class WorkflowStep:
    """Workflow step descriptor."""

    step_id: str
    name: str
    status: StepStatus = StepStatus.PENDING
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class UpgradePlan:
    """Upgrade plan."""

    plan_id: str
    source: OeVersion
    target: OeVersion
    path: UpgradePath
    steps: list[WorkflowStep] = field(default_factory=list)


@dataclass
class UpgradeTask:
    """Upgrade task state."""

    task_id: str
    host_id: str
    plan: UpgradePlan
    status: TaskStatus = TaskStatus.CREATED
    checkpoint: str | None = None
