"""Actor framework core."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4


class ActorFrameworkError(RuntimeError):
    """Base actor framework error."""


class ActorNotFoundError(ActorFrameworkError):
    """Raised when an actor cannot be resolved."""


class ActorAlreadyRegisteredError(ActorFrameworkError):
    """Raised when an actor id is already registered."""


class ActorExecutionError(ActorFrameworkError):
    """Raised when an actor fails to handle a message."""

    def __init__(self, actor_id: str, message_type: str, original: Exception) -> None:
        self.actor_id = actor_id
        self.message_type = message_type
        self.original = original
        super().__init__(f"actor {actor_id} failed to handle {message_type}: {original}")


@dataclass(frozen=True)
class ActorMessage:
    """Message payload sent to actors."""

    message_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActorEnvelope:
    """Message envelope with routing metadata."""

    target: str
    message: ActorMessage
    sender: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ActorResult:
    """Result returned by an actor."""

    actor_id: str
    message_type: str
    correlation_id: str
    value: Any = None


class Actor(Protocol):
    """Actor contract."""

    @property
    def actor_id(self) -> str:
        """Return the actor id."""

    def handle(self, envelope: ActorEnvelope) -> Any:
        """Handle one message."""


class BaseActor:
    """Convenience base actor."""

    def __init__(self, actor_id: str) -> None:
        self._actor_id = actor_id

    @property
    def actor_id(self) -> str:
        """Return the actor id."""
        return self._actor_id

    def handle(self, envelope: ActorEnvelope) -> Any:
        """Handle one message."""
        raise NotImplementedError


class InMemoryMailbox:
    """FIFO mailbox for actor envelopes."""

    def __init__(self) -> None:
        self._queue: deque[ActorEnvelope] = deque()

    def send(self, envelope: ActorEnvelope) -> None:
        """Append an envelope to the mailbox."""
        self._queue.append(envelope)

    def receive(self) -> ActorEnvelope | None:
        """Return the next envelope, if any."""
        if not self._queue:
            return None
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)


class ActorRegistry:
    """Actor registry."""

    def __init__(self) -> None:
        self._actors: dict[str, Actor] = {}

    def register(self, actor: Actor) -> None:
        """Register an actor."""
        if actor.actor_id in self._actors:
            raise ActorAlreadyRegisteredError(f"actor already registered: {actor.actor_id}")
        self._actors[actor.actor_id] = actor

    def get(self, actor_id: str) -> Actor:
        """Resolve an actor by id."""
        try:
            return self._actors[actor_id]
        except KeyError as exc:
            raise ActorNotFoundError(f"actor not found: {actor_id}") from exc

    def contains(self, actor_id: str) -> bool:
        """Return whether an actor is registered."""
        return actor_id in self._actors


class ActorSystem:
    """Synchronous actor system for CLI execution."""

    def __init__(
        self,
        registry: ActorRegistry | None = None,
        mailbox: InMemoryMailbox | None = None,
    ) -> None:
        self._registry = registry or ActorRegistry()
        self._mailbox = mailbox or InMemoryMailbox()

    @property
    def pending_messages(self) -> int:
        """Return the number of pending envelopes."""
        return len(self._mailbox)

    def register(self, actor: Actor) -> None:
        """Register an actor."""
        self._registry.register(actor)

    def tell(
        self,
        target: str,
        message: ActorMessage,
        sender: str | None = None,
        correlation_id: str | None = None,
    ) -> ActorEnvelope:
        """Queue a message without dispatching it."""
        if not self._registry.contains(target):
            raise ActorNotFoundError(f"actor not found: {target}")
        envelope = ActorEnvelope(
            target=target,
            message=message,
            sender=sender,
            correlation_id=correlation_id or str(uuid4()),
        )
        self._mailbox.send(envelope)
        return envelope

    def ask(
        self,
        target: str,
        message: ActorMessage,
        sender: str | None = None,
        correlation_id: str | None = None,
    ) -> ActorResult:
        """Dispatch one message immediately and return the result."""
        envelope = ActorEnvelope(
            target=target,
            message=message,
            sender=sender,
            correlation_id=correlation_id or str(uuid4()),
        )
        return self._dispatch(envelope)

    def run_once(self) -> ActorResult | None:
        """Dispatch one queued envelope."""
        envelope = self._mailbox.receive()
        if envelope is None:
            return None
        return self._dispatch(envelope)

    def drain(self) -> list[ActorResult]:
        """Dispatch all queued envelopes."""
        results: list[ActorResult] = []
        while True:
            result = self.run_once()
            if result is None:
                return results
            results.append(result)

    def _dispatch(self, envelope: ActorEnvelope) -> ActorResult:
        actor = self._registry.get(envelope.target)
        try:
            value = actor.handle(envelope)
        except Exception as exc:  # noqa: BLE001 - framework boundary stores arbitrary actor failure.
            raise ActorExecutionError(
                actor.actor_id,
                envelope.message.message_type,
                exc,
            ) from exc

        return ActorResult(
            actor_id=actor.actor_id,
            message_type=envelope.message.message_type,
            correlation_id=envelope.correlation_id,
            value=value,
        )
