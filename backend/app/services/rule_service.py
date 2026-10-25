import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.rule import FraudRule
from backend.app.schemas.rule import RuleUpdate

logger = logging.getLogger(__name__)

class RuleService:

    @staticmethod
    def get_all_rules(db: Session) -> List[FraudRule]:
        return db.query(FraudRule).order_by(FraudRule.rule_id.asc()).all()

    @staticmethod
    def get_rule_by_code(db: Session, rule_code: str) -> Optional[FraudRule]:
        return db.query(FraudRule).filter(FraudRule.rule_code == rule_code).first()

    @staticmethod
    def update_rule(db: Session, rule_id: int, payload: RuleUpdate) -> FraudRule:
        rule = db.query(FraudRule).filter(FraudRule.rule_id == rule_id).first()
        if not rule:
            raise ValueError(f"Rule with ID {rule_id} not found.")

        if payload.rule_name is not None:
            rule.rule_name = payload.rule_name
        if payload.description is not None:
            rule.description = payload.description
        if payload.risk_points is not None:
            rule.risk_points = payload.risk_points
        if payload.is_enabled is not None:
            rule.is_enabled = payload.is_enabled
        if payload.parameters_json is not None:
            # Merge existing parameters with updated parameters
            current_params = rule.parameters_json or {}
            current_params.update(payload.parameters_json)
            rule.parameters_json = current_params

        db.commit()
        db.refresh(rule)
        return rule
