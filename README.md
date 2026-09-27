# House Price Prediction - Cloud DataOps & REST API Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-18%20Passed-brightgreen.svg)]()

> **Course Assignment**: M-Tech Software Engineering / Cloud Computing  
> **Course Module**: API Driven Architecture & Cloud Data Pipelines (Assignment 1)  
> **Group**: Group-76  
> **Total Marks**: 15 (Part A: 10 marks | Part B: 5 marks)  

---

## 1. Executive Summary & Business Understanding

Real estate pricing is subject to complex multi-factor valuation drivers including square footage, property age, physical condition, and view quality. Traditional manual valuations are slow, error-prone, and fail to adapt to live market trends.

This project delivers a production-grade, cloud-native **DataOps and Machine Learning system** that:
1. **Automates the data lifecycle**: Ingests, validates, cleans, scales, analyzes, and retrains predictive models every **2 minutes** on a scheduled cadence (Part A).
2. **Exposes complete programmatic access**: Provides high-performance REST APIs displaying comprehensive application and DataOps details (Part B).
3. **Serves an interactive cloud dashboard**: Visualizes live 2-minute audit trails, EDA charts, ML benchmark comparisons, and real-time house valuation inference.

---

## 2. Assignment Rubric Mapping

### Part A: Automated Data Pipeline (10 Marks)

| Rubric Requirement | Implementation Details | Source Code Reference |
| :--- | :--- | :--- |
| **Data Ingestion (1.1)** | Automated schema detection, multi-column validation, robust missing file handling from Kaggle HouseData (4,600 rows, 18 columns). | `pipeline/ingestion.py` |
| **Preprocessing & Quality (1.2 & 1.3)** | Removed 49 invalid `price = $0` rows; median/mode imputation audit; 8-point summary statistics; Z-score feature scaling via `StandardScaler`. | `pipeline/preprocessing.py` |
| **Exploratory Data Analysis (EDA)** | Univariate price distributions, bivariate living area correlations, Pearson matrix heatmaps, binning (living space, age), and Random Forest feature ranking. | `pipeline/eda.py` |
| **Model Comparison & Selection** | Evaluates **Baseline (Linear Regression)** vs **Improved (Random Forest)** across MAE, RMSE, and R² score. Best model serialized via Joblib. | `pipeline/model.py` |
| **2-Minute Pipeline Automation** | `APScheduler` background interval scheduler triggering end-to-end execution every 120 seconds, with structured JSONL and SQLite audit logs. | `pipeline/runner.py` |

### Part B: API Access & Application Details (5 Marks)

The assignment requires exposing/retrieving important details of the application through APIs, displaying at least four such details, and testing them:

| # | Application Detail | HTTP Method | Endpoint | Description |
| :-: | :--- | :---: | :--- | :--- |
| **1** | **Application Details** | `GET` | `/api/application` | App name, version, runtime, environment, and tech stack details. |
| **2** | **Pipeline Status & Cadence** | `GET` | `/api/pipeline/status` | Current status, total runs, success rate, and 2-minute scheduler details. |
| **3** | **Execution History Audit** | `GET` | `/api/pipeline/history` | Chronological execution logs with run IDs, durations, statuses, and counts. |
| **4** | **Dataset & Preprocessing Summary**| `GET` | `/api/dataset/summary` | Schema, data types, missing value audit, and 8-point descriptive statistics. |
| **5** | **EDA Analytics** | `GET` | `/api/eda/summary` | Pearson correlation matrix, feature importance rankings, and binning counts. |
| **6** | **ML Model Benchmarks** | `GET` | `/api/model/metrics` | Model comparison table (MAE, RMSE, R² scores for Linear Regression vs RF). |
| **7** | **Manual Pipeline Trigger** | `POST` | `/api/pipeline/trigger` | Triggers immediate asynchronous pipeline run in background (HTTP 202). |
| **8** | **Live Inference Engine** | `POST` | `/api/predict` | Computes property valuation based on 11 input attributes. |
| **9** | **Health Check Probe** | `GET` | `/api/health` | Container & cloud liveness probe. |
| **10** | **Cloud Deployment Details** | `GET` | `/api/cloud/deployment` | Live AWS infrastructure via **built-in AWS APIs**: EC2 `DescribeInstances`, API Gateway `GetApis`, CloudWatch Logs `DescribeLogStreams`, Cost Explorer `GetCostAndUsage`. |

> **Rubric 3.1 note:** `/api/cloud/deployment` is the endpoint that satisfies *"use built-in APIs to access important application information (e.g. flow, deployment)"*. It does not invent its own data - it calls AWS's own service APIs through `boto3` and returns what they report. Every section degrades gracefully to an explanatory note when credentials are absent, so the endpoint returns HTTP 200 both on a laptop and on EC2.

---

## 3. Architecture & Tech Stack

```
                                  +---------------------------------------+
                                  |     Web Browser / Postman Client      |
                                  +---------------------------------------+
                                                     |
                                            HTTP (Port 8000)
                                                     v
                                  +---------------------------------------+
                                  |         FastAPI REST API Layer        |
                                  |    (/docs, /api/*, /static, /reports)  |
                                  +---------------------------------------+
                                       |                             |
                                (API Queries)               (Trigger / Lifecycle)
                                       v                             v
               +----------------------------------+        +---------------------------+
               |        SQLite Audit Store        |        |    APScheduler (2-Min)    |
               |  (pipeline_runs, pipeline_events)|        |    & Pipeline Orchestrator|
               +----------------------------------+        +---------------------------+
                                                                     |
                                  +----------------------------------+
                                  |
                                  v
+------------------+     +--------------------+     +-------------------+     +--------------------+
| 1. Ingestion     | --> | 2. Preprocessing   | --> | 3. Automated EDA  | --> | 4. Model Training  |
| - Kaggle CSV     |     | - Drop 49 price=0  |     | - Pearson Matrix  |     | - Linear Regression|
| - Schema Checks  |     | - Imputation       |     | - Binning & City  |     | - Random Forest    |
| - Error Handling |     | - StandardScaler   |     | - Static Charts   |     | - Joblib Model Save|
+------------------+     +--------------------+     +-------------------+     +--------------------+
```

---

## 4. Setup and Execution Guide

### Prerequisites
- Python 3.10+ (tested on Python 3.10+)
- Pip

### Option A: Local Run (Recommended)

1. **Clone or Navigate to the Directory**:
   ```bash
   cd API-Assignment-1-Group-76
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Application**:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

4. **Access the Application**:
   - **Cloud Monitoring Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
   - **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   - **Alternative ReDoc UI**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Option B: Docker Container

```bash
# Build image
docker build -t house-price-dataops:latest .

# Run container
docker run -p 8000:8000 --name dataops-app house-price-dataops:latest
```

Or using Docker Compose:
```bash
docker-compose up -d
```

---

## 5. Automated Verification & Testing

### Running the Test Suite
Execute the comprehensive Pytest suite:
```bash
python -m pytest tests/ -v
```
All 18 unit and integration tests validate:
- Ingestion schema validation, missing-file handling, and data-quality simulation
- Preprocessing median imputation, zero-price cleanup, outlier removal, and scaling
- EDA chart generation, correlation computation, and all four encoding techniques
- REST API response schemas, status codes, and Pydantic validation
- Selected-model metric consistency and graceful AWS degradation

`tests/conftest.py` executes one pipeline run before the suite starts, so the
tests are reproducible from a fresh clone with no pre-existing artifacts.

### Live API Testing with Postman
Import the provided collection file:
- **`postman_collection.json`** into Postman or Thunder Client.
- Base URL is pre-configured to `http://127.0.0.1:8000` (change the `base_url`
  collection variable to your API Gateway URL when demonstrating the cloud deployment).
- All 12 requests carry Postman test scripts asserting the expected status code
  (200 / 202 / 422), JSON content type, response time, and required schema fields.
- Run the whole collection with **Runner** to produce the pass summary screenshot.

---

## 6. Project Directory Structure

```
API-Assignment-1-Group-76/
├── backend/
│   ├── __init__.py
│   └── main.py                 # FastAPI application, REST endpoints, CORS & lifespan
├── config/
│   ├── __init__.py
│   └── settings.py             # Pydantic SettingsConfigDict application configuration
├── data/
│   ├── raw/
│   │   └── data.csv            # Kaggle HouseData (4,600 raw records)
│   └── processed/
│       └── clean_data.csv      # Cleaned and scaled dataset (4,551 records)
├── logs/
│   ├── pipeline_runs.db        # SQLite database (audit trails & stage events)
│   └── pipeline_structured.jsonl # JSON Lines structured application logs
├── models/
│   └── house_price_model.joblib # Serialized production machine learning model
├── pipeline/
│   ├── __init__.py
│   ├── ingestion.py            # Step 1: Data ingestion & schema audit
│   ├── preprocessing.py        # Step 2: Quality checks, imputation & scaling
│   ├── eda.py                  # Step 3: Statistical analysis & chart generation
│   ├── model.py                # Step 4: Baseline vs improved model evaluation
│   ├── runner.py               # Pipeline orchestrator & APScheduler 2-minute cadence
│   └── logger.py               # Structured SQLite & JSON logging engine
├── reports/
│   ├── eda_charts/             # Generated PNG statistical charts
│   ├── eda_summary.json        # Correlation & feature importance rankings
│   ├── model_comparison.json   # Model evaluation benchmarks (MAE, RMSE, R²)
│   └── summary_statistics.json # 8-point statistical summary per feature
├── static/
│   ├── index.html              # Cloud monitoring dashboard HTML
│   ├── style.css               # Glassmorphism dark theme CSS
│   └── app.js                  # Dynamic polling, countdown, tabs & inference logic
├── tests/
│   ├── test_api.py             # API integration tests
│   ├── test_eda.py             # EDA pipeline unit tests
│   ├── test_ingestion.py       # Ingestion unit tests
│   └── test_preprocessing.py   # Preprocessing unit tests
├── Dockerfile                  # Container build recipe
├── docker-compose.yml          # Container composition
├── postman_collection.json     # Pre-configured Postman test collection
├── requirements.txt            # Dependency manifest
└── README.md                   # Complete project documentation
```

---

## 7. Submission Checklist & Rubric Compliance

- [x] **Part A - Automated Pipeline**: Configured to run every 2 minutes via `APScheduler`.
- [x] **Part A - Ingestion & Preprocessing**: Cleaned 49 invalid records, imputed nulls, applied StandardScaler.
- [x] **Part A - EDA**: Generated 4 statistical charts and computed feature importance rankings.
- [x] **Part A - Model Benchmarking**: Trained and evaluated Linear Regression vs Random Forest.
- [x] **Part B - 4+ Application Details**: Exposes 9 endpoints (Application, Status, History, Summary, EDA, Metrics, Trigger, Predict, Health).
- [x] **Part B - Built-in APIs**: `/api/cloud/deployment` calls EC2, API Gateway, CloudWatch and Cost Explorer APIs via boto3.
- [x] **Part B - Automated Testing**: 18/18 Pytest tests passing; 12 Postman requests with assertions.
- [x] **Cloud Dashboard**: Modern glassmorphism UI with real-time countdown, audit logs, and interactive price prediction.
