"""Risk domain model."""

from dataclasses import dataclass, field
from typing import Any

from oe_lifecycle_manager.domain.common import RiskLevel


@dataclass
class CheckItem:
    """Pre-upgrade check definition."""

    code: str
    category: str
    severity: RiskLevel


@dataclass
class CheckResult:
    """Pre-upgrade check result."""

    check_code: str
    status: str
    risk_level: RiskLevel
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskReport:
    """Aggregated risk report."""

    task_id: str
    risk_level: RiskLevel
    score: int
    results: list[CheckResult] = field(default_factory=list)
