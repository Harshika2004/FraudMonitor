from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class DatasetOut(BaseModel):
    dataset_id: int
    filename: str
    file_size_bytes: int
    total_rows: int
    total_columns: int
    is_active: bool
    status: str
    created_at: datetime
    analyzed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class DatasetListResponse(BaseModel):
    items: List[DatasetOut]
    active_dataset_id: Optional[int] = None

class CSVPreviewResponse(BaseModel):
    filename: str
    file_size_bytes: int
    total_rows: int
    total_columns: int
    columns: List[str]
    preview_rows: List[Dict[str, Any]]
    missing_required_columns: List[str]
    detected_mappings: Dict[str, str]
    invalid_amounts_count: int
    invalid_timestamps_count: int
    duplicate_refs_count: int
    validation_passed: bool
    validation_summary: str
    temp_file_token: str

class CSVConfirmImportRequest(BaseModel):
    temp_file_token: str
    filename: str
    file_size_bytes: int
    column_mapping: Optional[Dict[str, str]] = None  # user overrides, e.g. {"account_id": "account_number"}

class AnalysisProgressResponse(BaseModel):
    dataset_id: int
    status: str
    total_transactions: int
    evaluated_transactions: int
    clean_transactions: int
    flagged_transactions: int
    open_alerts: int
    high_critical_alerts: int
    is_complete: bool
    message: str
