import os
import pytest
from pipeline.ingestion import DataIngestion
from config.settings import settings

def test_ingestion_valid_file():
    """Verify data ingestion loads rows, columns, and generates metadata."""
    ingestion = DataIngestion()
    df, meta = ingestion.ingest_data()
    
    assert df is not None
    assert len(df) == 4600
    assert len(df.columns) == 18
    assert meta["status"] == "SUCCESS"
    assert "price" in df.columns
    assert "sqft_living" in df.columns
    assert meta["rows"] == 4600

def test_ingestion_invalid_path():
    """Verify ingestion raises FileNotFoundError when path is wrong."""
    ingestion = DataIngestion(dataset_path="non_existent_file.csv")
    with pytest.raises(FileNotFoundError):
        ingestion.ingest_data()
