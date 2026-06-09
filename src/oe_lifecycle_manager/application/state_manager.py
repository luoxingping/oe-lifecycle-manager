"""State manager core framework."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from oe_lifecycle_manager.domain.common import StepStatus, TaskStatus
from oe_lifecycle_manager.domain.upgrade import UpgradeTask


class StateManagerError(RuntimeError):
    """Base state manager error."""


class TaskNotFoundError(StateManagerError):
    """Raised when a task snapshot is missing."""


class InvalidStateTransitionError(StateManagerError):
    """Raised when a task state transition is not allowed."""


@dataclass(frozen=True)
class StateEvent:
    """Immutable state transition event."""

    task_id: str
    from_status: TaskStatus
    to_status: TaskStatus
    checkpoint: str | None
    reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class TaskSnapshot:
    """Durable task state snapshot."""

    task_id: str
    status: TaskStatus
    checkpoint: str | None
    step_statuses: dict[str, StepStatus]


class StateStore(Protocol):
    """Persistence port for task state."""

    def save_snapshot(self, task: UpgradeTask) -> None:
        """Persist the latest task snapshot."""

    def load_snapshot(self, task_id: str) -> TaskSnapshot:
        """Load the latest task snapshot."""

    def append_event(self, event: StateEvent) -> None:
        """Persist a state event."""

    def list_events(self, task_id: str) -> list[StateEvent]:
        """List state events for a task."""


class InMemoryStateStore:
    """In-memory state store for CLI validation and unit tests."""

    def __init__(self) -> None:
        self._snapshots: dict[str, TaskSnapshot] = {}
        self._events: dict[str, list[StateEvent]] = {}

    def save_snapshot(self, task: UpgradeTask) -> None:
        """Persist the latest task snapshot."""
        self._snapshots[task.task_id] = TaskSnapshot(
            task_id=task.task_id,
            status=task.status,
            checkpoint=task.checkpoint,
            step_statuses={step.step_id: step.status for step in task.plan.steps},
        )

    def load_snapshot(self, task_id: str) -> TaskSnapshot:
        """Load the latest task snapshot."""
        try:
            return deepcopy(self._snapshots[task_id])
        except KeyError as exc:
            raise TaskNotFoundError(f"task snapshot not found: {task_id}") from exc

    def append_event(self, event: StateEvent) -> None:
        """Persist a state event."""
        self._events.setdefault(event.task_id, []).append(event)

    def list_events(self, task_id: str) -> list[StateEvent]:
        """List state events for a task."""
        return list(self._events.get(task_id, []))


class StateTransitionPolicy:
    """Task state transition policy."""

    _allowed: dict[TaskStatus, set[TaskStatus]] = {
        TaskStatus.CREATED: {
            TaskStatus.INVENTORY_COLLECTING,
            TaskStatus.CANCELLED,
        },
        TaskStatus.INVENTORY_COLLECTING: {
            TaskStatus.PRECHECK_RUNNING,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
        },
        TaskStatus.PRECHECK_RUNNING: {
            TaskStatus.RISK_ANALYZING,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
        },
        TaskStatus.RISK_ANALYZING: {
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.BLOCKED,
            TaskStatus.FAILED,
        },
        TaskStatus.WAITING_APPROVAL: {
            TaskStatus.ROLLBACK_POINT_CREATING,
            TaskStatus.CANCELLED,
        },
        TaskStatus.ROLLBACK_POINT_CREATING: {
            TaskStatus.UPGRADING,
            TaskStatus.FAILED,
        },
        TaskStatus.UPGRADING: {
            TaskStatus.REBOOT_REQUIRED,
            TaskStatus.POSTCHECK_RUNNING,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.RESUMABLE,
        },
        TaskStatus.REBOOT_REQUIRED: {
            TaskStatus.POSTCHECK_RUNNING,
            TaskStatus.RESUMABLE,
            TaskStatus.FAILED,
        },
        TaskStatus.POSTCHECK_RUNNING: {
            TaskStatus.COMPLETED,
            TaskStatus.DEGRADED,
            TaskStatus.FAILED,
        },
        TaskStatus.FAILED: {
            TaskStatus.RESUMABLE,
            TaskStatus.ROLLBACKING,
        },
        TaskStatus.RESUMABLE: {
            TaskStatus.UPGRADING,
            TaskStatus.ROLLBACKING,
            TaskStatus.FAILED,
        },
        TaskStatus.DEGRADED: {
            TaskStatus.COMPLETED,
            TaskStatus.ROLLBACKING,
        },
        TaskStatus.BLOCKED: {
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.CANCELLED,
        },
        TaskStatus.ROLLBACKING: {
            TaskStatus.ROLLED_BACK,
            TaskStatus.FAILED,
        },
        TaskStatus.COMPLETED: set(),
        TaskStatus.ROLLED_BACK: set(),
        TaskStatus.CANCELLED: set(),
    }

    def can_transition(self, current: TaskStatus, target: TaskStatus) -> bool:
        """Return whether a transition is allowed."""
        return target in self._allowed[current]

    def ensure_allowed(self, current: TaskStatus, target: TaskStatus) -> None:
        """Raise if a transition is not allowed."""
        if not self.can_transition(current, target):
            raise InvalidStateTransitionError(
                f"invalid task state transition: {current.value} -> {target.value}"
            )


class StateManager:
    """Coordinates task state transitions and snapshots."""

    def __init__(
        self,
        store: StateStore | None = None,
        policy: StateTransitionPolicy | None = None,
    ) -> None:
        self._store = store or InMemoryStateStore()
        self._policy = policy or StateTransitionPolicy()

    def register(self, task: UpgradeTask) -> TaskSnapshot:
        """Persist an initial task snapshot."""
        self._store.save_snapshot(task)
        return self._store.load_snapshot(task.task_id)

    def transition(
        self,
        task: UpgradeTask,
        target: TaskStatus,
        checkpoint: str | None = None,
        reason: str = "",
    ) -> StateEvent:
        """Move a task to another state and persist the change."""
        previous = task.status
        self._policy.ensure_allowed(previous, target)

        task.status = target
        if checkpoint is not None:
            task.checkpoint = checkpoint

        event = StateEvent(
            task_id=task.task_id,
            from_status=previous,
            to_status=target,
            checkpoint=task.checkpoint,
            reason=reason,
        )
        self._store.append_event(event)
        self._store.save_snapshot(task)
        return event

    def save_checkpoint(self, task: UpgradeTask, checkpoint: str) -> TaskSnapshot:
        """Persist a task checkpoint without changing task status."""
        task.checkpoint = checkpoint
        self._store.save_snapshot(task)
        return self._store.load_snapshot(task.task_id)

    def save_step_status(
        self,
        task: UpgradeTask,
        step_id: str,
        status: StepStatus,
        error: str | None = None,
    ) -> TaskSnapshot:
        """Persist one workflow step status."""
        step = self._find_step(task, step_id)
        step.status = status
        step.error = error
        task.checkpoint = step_id
        self._store.save_snapshot(task)
        return self._store.load_snapshot(task.task_id)

    def load_snapshot(self, task_id: str) -> TaskSnapshot:
        """Load the latest task snapshot."""
        return self._store.load_snapshot(task_id)

    def list_events(self, task_id: str) -> list[StateEvent]:
        """List state transition events."""
        return self._store.list_events(task_id)

    def _find_step(self, task: UpgradeTask, step_id: str):
        for step in task.plan.steps:
            if step.step_id == step_id:
                return step
        raise StateManagerError(f"workflow step not found: {step_id}")
