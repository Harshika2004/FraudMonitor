from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.database.connection import get_db
from backend.app.services.dataset_service import DatasetService
from backend.app.schemas.dataset import (
    DatasetOut,
    DatasetListResponse,
    CSVPreviewResponse,
    CSVConfirmImportRequest,
    AnalysisProgressResponse
)

router = APIRouter(prefix="/datasets", tags=["Datasets"])

@router.get("", response_model=DatasetListResponse)
def list_datasets(db: Session = Depends(get_db)):
    """List all imported datasets and indicate the active one."""
    datasets = DatasetService.get_all_datasets(db)
    active = DatasetService.get_active_dataset(db)
    return {
        "items": datasets,
        "active_dataset_id": active.dataset_id if active else None
    }

@router.get("/active", response_model=Optional[DatasetOut])
def get_active_dataset(db: Session = Depends(get_db)):
    """Retrieve details of the currently active dataset."""
    active = DatasetService.get_active_dataset(db)
    return active

@router.post("/switch/{dataset_id}", response_model=DatasetOut)
def switch_active_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Switches the active dataset without altering historical data."""
    ds = DatasetService.set_active_dataset(db, dataset_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset with ID {dataset_id} not found."
        )
    return ds

@router.post("/preview", response_model=CSVPreviewResponse)
async def preview_csv(file: UploadFile = File(...)):
    """
    Validates uploaded CSV file, computes preview rows and structural errors,
    and returns a preview token for user confirmation.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a valid CSV file (.csv)."
        )

    content_bytes = await file.read()
    file_size = len(content_bytes)
    content_str = content_bytes.decode("utf-8", errors="replace")

    preview_res = DatasetService.preview_csv(
        file_content_str=content_str,
        filename=file.filename,
        file_size=file_size
    )
    return preview_res

@router.post("/confirm", response_model=DatasetOut)
def confirm_import(payload: CSVConfirmImportRequest, db: Session = Depends(get_db)):
    """
    Confirms CSV upload, creates dataset record, and ingests all rows
    linked to the new dataset.
    """
    try:
        dataset = DatasetService.confirm_and_import(
            db=db,
            temp_file_token=payload.temp_file_token,
            filename=payload.filename,
            file_size=payload.file_size_bytes,
            custom_mapping=payload.column_mapping
        )
        return dataset
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Import failed: {str(e)}")

@router.post("/{dataset_id}/analyze", response_model=AnalysisProgressResponse)
def analyze_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """
    Runs deterministic fraud detection engine across all transactions
    belonging to the dataset and generates explainable alerts.
    """
    try:
        result = DatasetService.run_analysis(db, dataset_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Analysis failed: {str(e)}")
