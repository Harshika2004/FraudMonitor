from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.models.transaction import Transaction

@dataclass
class RuleEvaluationResult:
    """Standardized result returned by every fraud detection rule."""
    rule_code: str
    rule_name: str
    triggered: bool
    points: int
    reason: str
    parameters_used: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    insufficient_data: bool = False

class BaseFraudRule(ABC):
    """Abstract Base Class for all configurable fraud detection rules."""
    def __init__(self, rule_code: str, rule_name: str, default_points: int):
        self.rule_code = rule_code
        self.rule_name = rule_name
        self.default_points = default_points

    @abstractmethod
    def evaluate(
        self,
        transaction: Transaction,
        db: Session,
        parameters: Optional[Dict[str, Any]] = None,
        configured_points: Optional[int] = None
    ) -> RuleEvaluationResult:
        """
        Evaluate a transaction deterministically against the rule logic.
        """
        pass
