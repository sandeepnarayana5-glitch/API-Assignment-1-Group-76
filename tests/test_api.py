import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    """Verify health endpoint returns 200 OK."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "HEALTHY"

def test_application_info_endpoint():
    """Verify application details endpoint returns 200 OK."""
    response = client.get("/api/application")
    assert response.status_code == 200
    data = response.json()
    assert "application_name" in data
    assert "version" in data
    assert "tech_stack" in data

def test_pipeline_status_endpoint():
    """Verify pipeline status endpoint returns 200 OK."""
    response = client.get("/api/pipeline/status")
    assert response.status_code == 200
    data = response.json()
    assert "current_status" in data
    assert "total_runs" in data
    assert "scheduler" in data

def test_pipeline_history_endpoint():
    """Verify pipeline execution history endpoint returns 200 OK."""
    response = client.get("/api/pipeline/history?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "history" in data
    assert isinstance(data["history"], list)

def test_dataset_summary_endpoint():
    """Verify dataset summary endpoint returns 200 OK."""
    response = client.get("/api/dataset/summary")
    assert response.status_code == 200
    data = response.json()
    assert "dataset_name" in data
    assert "summary_statistics" in data

def test_eda_summary_endpoint():
    """Verify EDA summary endpoint returns 200 OK."""
    response = client.get("/api/eda/summary")
    assert response.status_code == 200
    data = response.json()
    assert "correlation_summary" in data
    assert "feature_importance_ranking" in data

def test_model_metrics_endpoint():
    """Verify model metrics endpoint returns 200 OK."""
    response = client.get("/api/model/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "baseline_model" in data
    assert "improved_model" in data
    assert "r2" in data["baseline_model"]

def test_predict_endpoint_valid():
    """Verify predict endpoint calculates price for valid house features."""
    payload = {
        "bedrooms": 3.0,
        "bathrooms": 2.0,
        "sqft_living": 2100.0,
        "sqft_lot": 6500.0,
        "floors": 1.5,
        "waterfront": 0,
        "view": 1,
        "condition": 4,
        "sqft_above": 1800.0,
        "sqft_basement": 300.0,
        "property_age": 30.0
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "predicted_price" in data
    assert data["predicted_price"] > 0
    assert data["currency"] == "USD"

def test_predict_endpoint_invalid():
    """Verify predict endpoint handles invalid feature data with 422 Unprocessable Entity."""
    payload = {
        "bedrooms": -5.0,  # Invalid negative bedrooms
        "sqft_living": "invalid_string"
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 422

def test_cloud_deployment_endpoint():
    """Verify the AWS built-in API endpoint always returns 200, with or without credentials."""
    response = client.get("/api/cloud/deployment")
    assert response.status_code == 200
    data = response.json()
    assert "aws_region" in data
    assert "compute_instance" in data
    assert "cloudwatch_logging" in data

def test_model_metrics_reports_selected_model():
    """Verify metrics expose the SELECTED model's scores, not always the Random Forest."""
    response = client.get("/api/model/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "selected_metrics" in data
    chosen = data["selected_model"]
    key = "improved_model" if "Forest" in chosen else "baseline_model"
    assert data["selected_metrics"]["r2"] == data[key]["r2"]

def test_eda_summary_includes_encoding():
    """Verify categorical encoding (rubric 1.4) is present in the EDA output."""
    response = client.get("/api/eda/summary")
    assert response.status_code == 200
    enc = response.json()["encoding_summary"]
    assert len(enc) >= 3
    techniques = " ".join(v["technique"] for v in enc.values())
    assert "One-Hot" in techniques
    assert "Frequency" in techniques
