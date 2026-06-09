"""Workflow engine core framework."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from oe_lifecycle_manager.domain.common import StepStatus, TaskStatus
from oe_lifecycle_manager.domain.upgrade import UpgradeTask, WorkflowStep

WorkflowHandler = Callable[["WorkflowContext"], None]


class WorkflowError(RuntimeError):
    """Base workflow engine error."""


class WorkflowDefinitionError(WorkflowError):
    """Raised when a workflow definition is invalid."""


class WorkflowExecutionError(WorkflowError):
    """Raised when a workflow step fails."""

    def __init__(self, task_id: str, step_id: str, original: Exception) -> None:
        self.task_id = task_id
        self.step_id = step_id
        self.original = original
        super().__init__(f"workflow task {task_id} failed at step {step_id}: {original}")


@dataclass
class WorkflowContext:
    """Runtime context passed to workflow handlers."""

    task: UpgradeTask
    step: WorkflowStep
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowExecutionResult:
    """Workflow execution result."""

    task_id: str
    status: TaskStatus
    checkpoint: str | None
    completed_steps: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowDefinition:
    """Executable workflow definition."""

    handlers: dict[str, WorkflowHandler]

    @classmethod
    def from_handlers(cls, handlers: dict[str, WorkflowHandler]) -> "WorkflowDefinition":
        """Create a workflow definition from step handlers."""
        return cls(handlers=dict(handlers))


class WorkflowEngine:
    """Executes workflow steps in order.

    The engine only owns execution orchestration and in-memory state mutation.
    Durable state persistence is intentionally left to the State Manager module.
    """

    def start(
        self,
        task: UpgradeTask,
        definition: WorkflowDefinition,
        data: dict[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        """Start a workflow from the first unfinished step."""
        self._validate(task, definition)
        task.status = TaskStatus.UPGRADING
        return self._run_steps(task, definition, self._pending_steps(task.plan.steps), data)

    def resume(
        self,
        task: UpgradeTask,
        definition: WorkflowDefinition,
        data: dict[str, Any] | None = None,
    ) -> WorkflowExecutionResult:
        """Resume a workflow from the first unfinished or failed step."""
        self._validate(task, definition)
        task.status = TaskStatus.RESUMABLE
        steps = self._resumable_steps(task.plan.steps)
        return self._run_steps(task, definition, steps, data)

    def _run_steps(
        self,
        task: UpgradeTask,
        definition: WorkflowDefinition,
        steps: Iterable[WorkflowStep],
        data: dict[str, Any] | None,
    ) -> WorkflowExecutionResult:
        runtime_data = data if data is not None else {}

        for step in steps:
            handler = definition.handlers[step.step_id]
            step.status = StepStatus.RUNNING
            step.error = None
            task.checkpoint = step.step_id

            try:
                handler(WorkflowContext(task=task, step=step, data=runtime_data))
            except Exception as exc:  # noqa: BLE001 - framework boundary stores arbitrary handler failure.
                step.status = StepStatus.FAILED
                step.error = str(exc)
                task.status = TaskStatus.FAILED
                raise WorkflowExecutionError(task.task_id, step.step_id, exc) from exc

            step.status = StepStatus.SUCCEEDED
            task.checkpoint = step.step_id

        task.status = TaskStatus.COMPLETED
        return self._result(task)

    def _validate(self, task: UpgradeTask, definition: WorkflowDefinition) -> None:
        if not task.plan.steps:
            raise WorkflowDefinitionError("workflow must contain at least one step")

        seen: set[str] = set()
        for step in task.plan.steps:
            if step.step_id in seen:
                raise WorkflowDefinitionError(f"duplicate workflow step id: {step.step_id}")
            seen.add(step.step_id)
            if step.step_id not in definition.handlers:
                raise WorkflowDefinitionError(f"missing handler for workflow step: {step.step_id}")

    def _pending_steps(self, steps: list[WorkflowStep]) -> list[WorkflowStep]:
        return [step for step in steps if step.status in {StepStatus.PENDING, StepStatus.FAILED}]

    def _resumable_steps(self, steps: list[WorkflowStep]) -> list[WorkflowStep]:
        return [step for step in steps if step.status != StepStatus.SUCCEEDED]

    def _result(self, task: UpgradeTask) -> WorkflowExecutionResult:
        completed = tuple(
            step.step_id for step in task.plan.steps if step.status == StepStatus.SUCCEEDED
        )
        return WorkflowExecutionResult(
            task_id=task.task_id,
            status=task.status,
            checkpoint=task.checkpoint,
            completed_steps=completed,
        )
