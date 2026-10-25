from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.services.rule_service import RuleService
from backend.app.schemas.rule import RuleOut, RuleUpdate

router = APIRouter(prefix="/rules", tags=["Fraud Rules"])

@router.get("", response_model=List[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    """Retrieve all fraud detection rules and their current configuration."""
    return RuleService.get_all_rules(db)

@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db)):
    """Update rule parameters, points, or enabled status."""
    try:
        return RuleService.update_rule(db, rule_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
