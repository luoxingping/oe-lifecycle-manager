"""Unit tests for the actor framework."""

from __future__ import annotations

import unittest

from oe_lifecycle_manager.application.actor_framework import (
    ActorAlreadyRegisteredError,
    ActorExecutionError,
    ActorMessage,
    ActorNotFoundError,
    ActorSystem,
    BaseActor,
)


class RecordingActor(BaseActor):
    """Actor that records received messages."""

    def __init__(self, actor_id: str) -> None:
        super().__init__(actor_id)
        self.received: list[str] = []

    def handle(self, envelope):
        self.received.append(envelope.message.message_type)
        return {
            "handled_by": self.actor_id,
            "message_type": envelope.message.message_type,
            "payload": envelope.message.payload,
        }


class FailingActor(BaseActor):
    """Actor that always fails."""

    def handle(self, envelope):
        raise RuntimeError("actor failed")


class ActorFrameworkTest(unittest.TestCase):
    """Actor framework unit tests."""

    def test_ask_dispatches_message_immediately(self) -> None:
        actor = RecordingActor("worker")
        system = ActorSystem()
        system.register(actor)

        result = system.ask(
            "worker",
            ActorMessage("collect", {"host_id": "host-1"}),
            correlation_id="corr-1",
        )

        self.assertEqual(result.actor_id, "worker")
        self.assertEqual(result.message_type, "collect")
        self.assertEqual(result.correlation_id, "corr-1")
        self.assertEqual(result.value["payload"], {"host_id": "host-1"})
        self.assertEqual(actor.received, ["collect"])
        self.assertEqual(system.pending_messages, 0)

    def test_tell_queues_message_and_drain_dispatches_fifo(self) -> None:
        actor = RecordingActor("worker")
        system = ActorSystem()
        system.register(actor)

        system.tell("worker", ActorMessage("first"))
        system.tell("worker", ActorMessage("second"))

        self.assertEqual(system.pending_messages, 2)
        results = system.drain()

        self.assertEqual([result.message_type for result in results], ["first", "second"])
        self.assertEqual(actor.received, ["first", "second"])
        self.assertEqual(system.pending_messages, 0)

    def test_run_once_returns_none_when_mailbox_is_empty(self) -> None:
        system = ActorSystem()

        self.assertIsNone(system.run_once())

    def test_tell_rejects_missing_actor(self) -> None:
        system = ActorSystem()

        with self.assertRaisesRegex(ActorNotFoundError, "missing"):
            system.tell("missing", ActorMessage("collect"))

    def test_ask_rejects_missing_actor(self) -> None:
        system = ActorSystem()

        with self.assertRaisesRegex(ActorNotFoundError, "missing"):
            system.ask("missing", ActorMessage("collect"))

    def test_register_rejects_duplicate_actor_id(self) -> None:
        system = ActorSystem()
        system.register(RecordingActor("worker"))

        with self.assertRaisesRegex(ActorAlreadyRegisteredError, "worker"):
            system.register(RecordingActor("worker"))

    def test_actor_failure_is_wrapped(self) -> None:
        system = ActorSystem()
        system.register(FailingActor("worker"))

        with self.assertRaises(ActorExecutionError) as exc_info:
            system.ask("worker", ActorMessage("collect"))

        self.assertEqual(exc_info.exception.actor_id, "worker")
        self.assertEqual(exc_info.exception.message_type, "collect")
        self.assertIsInstance(exc_info.exception.original, RuntimeError)


if __name__ == "__main__":
    unittest.main()
