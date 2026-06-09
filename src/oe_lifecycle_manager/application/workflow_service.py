"""Workflow application service."""

from __future__ import annotations

from oe_lifecycle_manager.application.workflow_engine import (
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowExecutionResult,
)
from oe_lifecycle_manager.domain.upgrade import UpgradeTask


class WorkflowService:
    """Coordinates workflow execution."""

    def __init__(self, engine: WorkflowEngine | None = None) -> None:
        self._engine = engine or WorkflowEngine()

    def start(
        self,
        task: UpgradeTask,
        definition: WorkflowDefinition,
        data: dict | None = None,
    ) -> WorkflowExecutionResult:
        """Start a workflow task."""
        return self._engine.start(task, definition, data)

    def resume(
        self,
        task: UpgradeTask,
        definition: WorkflowDefinition,
        data: dict | None = None,
    ) -> WorkflowExecutionResult:
        """Resume a workflow task."""
        return self._engine.resume(task, definition, data)
