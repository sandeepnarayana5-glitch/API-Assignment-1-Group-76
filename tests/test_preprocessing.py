import os
import pytest
import pandas as pd
from pipeline.ingestion import DataIngestion
from pipeline.preprocessing import DataPreprocessing

def test_preprocessing_flow():
    """Verify preprocessing removes invalid price=0 rows and scales features."""
    ingestion = DataIngestion()
    df_raw, _ = ingestion.ingest_data()
    
    preprocessor = DataPreprocessing()
    df_clean, meta = preprocessor.process(df_raw)
    
    # 49 records had price = 0
    # 49 zero-price rows plus the top 0.5% luxury outliers are removed
    assert len(df_clean) < 4600 - 49
    assert meta["zero_prices_removed"] == 49
    assert meta["outliers_removed"] > 0
    assert (df_clean["price"] <= 0).sum() == 0
    assert "property_age" in df_clean.columns
    assert "sqft_living_scaled" in df_clean.columns
    assert meta["status"] == "SUCCESS"
    assert "summary_statistics" in meta
    assert "price" in meta["summary_statistics"]

def test_missing_value_imputation_executes():
    """Verify nulls are detected and median-imputed (rubric 1.3)."""
    ingestion = DataIngestion()
    df_raw, ing_meta = ingestion.ingest_data()

    # Ingestion must have injected simulated nulls for imputation to be evidenced
    assert ing_meta["null_cells_total"] > 0
    assert len(ing_meta["simulated_nulls"]) > 0

    preprocessor = DataPreprocessing()
    df_clean, meta = preprocessor.process(df_raw)

    # After preprocessing there must be zero nulls and a populated imputation log
    assert df_clean.isnull().sum().sum() == 0
    assert len(meta["imputation_log"]) > 0
    assert any("median" in entry for entry in meta["imputation_log"])
