"""Unit tests for the state manager."""

from __future__ import annotations

import unittest

from oe_lifecycle_manager.application.state_manager import (
    InMemoryStateStore,
    InvalidStateTransitionError,
    StateManager,
    TaskNotFoundError,
)
from oe_lifecycle_manager.domain.common import OeVersion, StepStatus, TaskStatus
from oe_lifecycle_manager.domain.lifecycle import UpgradePath
from oe_lifecycle_manager.domain.upgrade import UpgradePlan, UpgradeTask, WorkflowStep


def make_task() -> UpgradeTask:
    """Create a minimal upgrade task for state manager tests."""
    source = OeVersion("22.03-SP1")
    target = OeVersion("22.03-SP2")
    path = UpgradePath(source=source, target=target)
    plan = UpgradePlan(
        plan_id="plan-1",
        source=source,
        target=target,
        path=path,
        steps=[
            WorkflowStep(step_id="collect", name="Collect inventory"),
            WorkflowStep(step_id="precheck", name="Run precheck"),
        ],
    )
    return UpgradeTask(task_id="task-1", host_id="host-1", plan=plan)


class StateManagerTest(unittest.TestCase):
    """State manager unit tests."""

    def test_register_saves_initial_snapshot(self) -> None:
        task = make_task()
        manager = StateManager()

        snapshot = manager.register(task)

        self.assertEqual(snapshot.task_id, "task-1")
        self.assertEqual(snapshot.status, TaskStatus.CREATED)
        self.assertIsNone(snapshot.checkpoint)
        self.assertEqual(
            snapshot.step_statuses,
            {"collect": StepStatus.PENDING, "precheck": StepStatus.PENDING},
        )

    def test_transition_persists_event_and_snapshot(self) -> None:
        task = make_task()
        manager = StateManager()
        manager.register(task)

        event = manager.transition(
            task,
            TaskStatus.INVENTORY_COLLECTING,
            checkpoint="collect",
            reason="start inventory",
        )
        snapshot = manager.load_snapshot(task.task_id)

        self.assertEqual(event.from_status, TaskStatus.CREATED)
        self.assertEqual(event.to_status, TaskStatus.INVENTORY_COLLECTING)
        self.assertEqual(event.checkpoint, "collect")
        self.assertEqual(event.reason, "start inventory")
        self.assertEqual(snapshot.status, TaskStatus.INVENTORY_COLLECTING)
        self.assertEqual(snapshot.checkpoint, "collect")
        self.assertEqual(len(manager.list_events(task.task_id)), 1)

    def test_invalid_transition_is_rejected(self) -> None:
        task = make_task()
        manager = StateManager()

        with self.assertRaisesRegex(InvalidStateTransitionError, "CREATED -> COMPLETED"):
            manager.transition(task, TaskStatus.COMPLETED)

        self.assertEqual(task.status, TaskStatus.CREATED)

    def test_terminal_state_cannot_transition(self) -> None:
        task = make_task()
        task.status = TaskStatus.COMPLETED
        manager = StateManager()

        with self.assertRaisesRegex(
            InvalidStateTransitionError,
            "COMPLETED -> ROLLBACKING",
        ):
            manager.transition(task, TaskStatus.ROLLBACKING)

    def test_save_checkpoint_does_not_change_status(self) -> None:
        task = make_task()
        task.status = TaskStatus.UPGRADING
        manager = StateManager()

        snapshot = manager.save_checkpoint(task, "precheck")

        self.assertEqual(task.status, TaskStatus.UPGRADING)
        self.assertEqual(task.checkpoint, "precheck")
        self.assertEqual(snapshot.status, TaskStatus.UPGRADING)
        self.assertEqual(snapshot.checkpoint, "precheck")

    def test_save_step_status_updates_checkpoint_and_snapshot(self) -> None:
        task = make_task()
        manager = StateManager()

        snapshot = manager.save_step_status(
            task,
            "precheck",
            StepStatus.FAILED,
            error="check failed",
        )

        self.assertEqual(task.checkpoint, "precheck")
        self.assertEqual(task.plan.steps[1].status, StepStatus.FAILED)
        self.assertEqual(task.plan.steps[1].error, "check failed")
        self.assertEqual(snapshot.step_statuses["precheck"], StepStatus.FAILED)

    def test_store_raises_when_snapshot_is_missing(self) -> None:
        store = InMemoryStateStore()

        with self.assertRaisesRegex(TaskNotFoundError, "missing-task"):
            store.load_snapshot("missing-task")


if __name__ == "__main__":
    unittest.main()
