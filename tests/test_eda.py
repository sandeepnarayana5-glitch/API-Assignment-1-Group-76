import os
import pytest
from pipeline.ingestion import DataIngestion
from pipeline.preprocessing import DataPreprocessing
from pipeline.eda import ExploratoryDataAnalysis

def test_eda_flow():
    """Verify EDA generates correlations, binning, feature importances, and chart files."""
    ingestion = DataIngestion()
    df_raw, _ = ingestion.ingest_data()
    
    preprocessor = DataPreprocessing()
    df_clean, _ = preprocessor.process(df_raw)
    
    eda = ExploratoryDataAnalysis()
    df_eda, meta = eda.analyze(df_clean)
    
    assert "correlation_summary" in meta
    assert len(meta["correlation_summary"]["top_positive_correlations"]) > 0
    assert "binning_summary" in meta
    assert "feature_importance_ranking" in meta
    assert len(meta["feature_importance_ranking"]) > 0
    
    # Verify generated chart files exist on disk
    assert os.path.exists("reports/eda_charts/correlation_heatmap.png")
    assert os.path.exists("reports/eda_charts/feature_importance.png")
    assert os.path.exists("reports/eda_charts/price_distribution.png")
    assert os.path.exists("reports/eda_charts/sqft_vs_price.png")

def test_eda_encoding_applied():
    """Verify one-hot, label, frequency and binary encoding are all produced."""
    ingestion = DataIngestion()
    df_raw, _ = ingestion.ingest_data()
    df_clean, _ = DataPreprocessing().process(df_raw)
    df_eda, meta = ExploratoryDataAnalysis().analyze(df_clean)

    enc = meta["encoding_summary"]
    assert "one_hot_condition" in enc
    assert "label_living_space_bin" in enc
    assert "frequency_city" in enc
    assert "binary_waterfront" in enc

    # Encoded columns must physically exist on the returned dataframe
    assert "city_frequency_encoded" in df_eda.columns
    assert "living_space_bin_encoded" in df_eda.columns
    assert any(c.startswith("condition_") for c in df_eda.columns)
