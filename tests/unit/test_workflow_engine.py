"""Unit tests for the workflow engine."""

from __future__ import annotations

import unittest

from oe_lifecycle_manager.application.workflow_engine import (
    WorkflowDefinition,
    WorkflowDefinitionError,
    WorkflowEngine,
    WorkflowExecutionError,
)
from oe_lifecycle_manager.domain.common import OeVersion, StepStatus, TaskStatus
from oe_lifecycle_manager.domain.lifecycle import UpgradePath
from oe_lifecycle_manager.domain.upgrade import UpgradePlan, UpgradeTask, WorkflowStep


def make_task(steps: list[WorkflowStep] | None = None) -> UpgradeTask:
    """Create a minimal upgrade task for workflow tests."""
    source = OeVersion("22.03-SP1")
    target = OeVersion("22.03-SP2")
    path = UpgradePath(source=source, target=target)
    plan = UpgradePlan(
        plan_id="plan-1",
        source=source,
        target=target,
        path=path,
        steps=steps
        or [
            WorkflowStep(step_id="collect", name="Collect inventory"),
            WorkflowStep(step_id="precheck", name="Run precheck"),
            WorkflowStep(step_id="upgrade", name="Run upgrade"),
        ],
    )
    return UpgradeTask(task_id="task-1", host_id="host-1", plan=plan)


class WorkflowEngineTest(unittest.TestCase):
    """Workflow engine unit tests."""

    def test_start_runs_steps_in_order_and_completes_task(self) -> None:
        task = make_task()
        executed: list[str] = []

        definition = WorkflowDefinition.from_handlers(
            {
                "collect": lambda context: executed.append(context.step.step_id),
                "precheck": lambda context: executed.append(context.step.step_id),
                "upgrade": lambda context: executed.append(context.step.step_id),
            }
        )

        result = WorkflowEngine().start(task, definition)

        self.assertEqual(executed, ["collect", "precheck", "upgrade"])
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.checkpoint, "upgrade")
        self.assertEqual(result.completed_steps, ("collect", "precheck", "upgrade"))
        self.assertEqual(
            [step.status for step in task.plan.steps],
            [StepStatus.SUCCEEDED, StepStatus.SUCCEEDED, StepStatus.SUCCEEDED],
        )

    def test_start_marks_failed_step_and_keeps_checkpoint(self) -> None:
        task = make_task()

        def fail(context) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("repo unavailable")

        definition = WorkflowDefinition.from_handlers(
            {
                "collect": lambda context: None,
                "precheck": fail,
                "upgrade": lambda context: None,
            }
        )

        with self.assertRaises(WorkflowExecutionError) as exc_info:
            WorkflowEngine().start(task, definition)

        self.assertEqual(exc_info.exception.task_id, "task-1")
        self.assertEqual(exc_info.exception.step_id, "precheck")
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertEqual(task.checkpoint, "precheck")
        self.assertEqual(task.plan.steps[0].status, StepStatus.SUCCEEDED)
        self.assertEqual(task.plan.steps[1].status, StepStatus.FAILED)
        self.assertEqual(task.plan.steps[1].error, "repo unavailable")
        self.assertEqual(task.plan.steps[2].status, StepStatus.PENDING)

    def test_resume_skips_succeeded_steps_and_retries_failed_step(self) -> None:
        task = make_task()
        task.plan.steps[0].status = StepStatus.SUCCEEDED
        task.plan.steps[1].status = StepStatus.FAILED
        task.checkpoint = "precheck"
        executed: list[str] = []

        definition = WorkflowDefinition.from_handlers(
            {
                "collect": lambda context: executed.append(context.step.step_id),
                "precheck": lambda context: executed.append(context.step.step_id),
                "upgrade": lambda context: executed.append(context.step.step_id),
            }
        )

        result = WorkflowEngine().resume(task, definition)

        self.assertEqual(executed, ["precheck", "upgrade"])
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.completed_steps, ("collect", "precheck", "upgrade"))

    def test_definition_requires_handler_for_every_step(self) -> None:
        task = make_task()
        definition = WorkflowDefinition.from_handlers({"collect": lambda context: None})

        with self.assertRaisesRegex(WorkflowDefinitionError, "missing handler"):
            WorkflowEngine().start(task, definition)

    def test_definition_rejects_duplicate_step_ids(self) -> None:
        task = make_task(
            [
                WorkflowStep(step_id="collect", name="Collect inventory"),
                WorkflowStep(step_id="collect", name="Collect inventory again"),
            ]
        )
        definition = WorkflowDefinition.from_handlers({"collect": lambda context: None})

        with self.assertRaisesRegex(WorkflowDefinitionError, "duplicate workflow step id"):
            WorkflowEngine().start(task, definition)


if __name__ == "__main__":
    unittest.main()
