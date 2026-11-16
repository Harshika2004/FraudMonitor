from backend.app.services.dataset_service import DatasetService
from backend.app.models.dataset import Dataset
from backend.app.models.transaction import Transaction

def test_dataset_service_preview_confirm_analyze(db_session):
    # 1. Preview
    csv_content = (
        "account_id,amount,transaction_type,timestamp,location_city\n"
        "ACC001,500.00,WITHDRAWAL,2026-11-01 10:00:00,New York\n"
        "ACC001,15000.00,TRANSFER,2026-11-01 11:00:00,New York\n"
        "ACC002,120.00,PAYMENT,2026-11-01 12:00:00,London\n"
    )
    preview = DatasetService.preview_csv(csv_content, "sample.csv", len(csv_content))
    assert preview["filename"] == "sample.csv"
    assert preview["total_rows"] == 3
    assert preview["validation_passed"] is True
    assert "Valid schema detected" in preview["validation_summary"]
    assert len(preview["preview_rows"]) == 3
    token = preview["temp_file_token"]

    # 2. Confirm and import
    ds = DatasetService.confirm_and_import(
        db=db_session,
        temp_file_token=token,
        filename="sample.csv",
        file_size_bytes=len(csv_content),
        custom_mapping={}
    )
    assert ds.dataset_id is not None
    assert ds.status == "UPLOADED"
    assert ds.is_active is True

    # Verify transactions linked to dataset
    txns = db_session.query(Transaction).filter(Transaction.dataset_id == ds.dataset_id).all()
    assert len(txns) == 3

    # 3. Run analysis
    res = DatasetService.run_analysis(db=db_session, dataset_id=ds.dataset_id)
    assert res["status"] == "ANALYSED"
    assert res["total_transactions"] == 3
    assert res["evaluated_transactions"] == 3
    assert ds.status == "ANALYSED"

    # 4. Check active dataset retrieval
    active = DatasetService.get_active_dataset(db_session)
    assert active is not None
    assert active.dataset_id == ds.dataset_id
