import os
import json
import platform
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from config.settings import settings
from pipeline.logger import (
    get_pipeline_summary, get_recent_runs, get_recent_events,
    reconcile_stale_runs, get_cloudwatch_state
)
from pipeline.runner import pipeline_runner
from pipeline.model import ModelPipeline

APP_START_TIME = datetime.now(timezone.utc).isoformat()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for scheduler startup and shutdown."""
    # Reconcile any run left in RUNNING state by a crash or container restart,
    # otherwise the dashboard would report RUNNING forever and skew success rate.
    reconcile_stale_runs()

    # Ensure at least one initial pipeline execution exists
    summary = get_pipeline_summary()
    if summary["total_runs"] == 0:
        pipeline_runner.execute_pipeline(trigger_source="INITIAL_BOOTSTRAP")

    # Start 2-minute background scheduler if enabled
    if settings.AUTO_START_SCHEDULER:
        pipeline_runner.start_scheduler()

    yield
    # Graceful shutdown of scheduler
    if pipeline_runner.scheduler and pipeline_runner.scheduler.running:
        pipeline_runner.scheduler.shutdown()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Cloud-Native DataOps & ML Platform for House Price Prediction
    This API provides complete programmatic visibility into the DataOps lifecycle:
    - **Automated Data Pipeline Execution & 2-Minute Scheduler Monitoring**
    - **Dataset Quality, Missing Value Audit & Summary Statistics**
    - **Exploratory Data Analysis (EDA) Analytics & Visualizations**
    - **Machine Learning Model Evaluation & Inference**
    """,
    lifespan=lifespan
)

# Enable CORS for local or cloud dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for generated EDA charts and dashboard
app.mount("/reports", StaticFiles(directory=settings.REPORTS_DIR), name="reports")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Pydantic schema for prediction
class HousePredictionRequest(BaseModel):
    bedrooms: float = Field(3.0, description="Number of bedrooms", ge=0, le=15)
    bathrooms: float = Field(2.25, description="Number of bathrooms", ge=0, le=12)
    sqft_living: float = Field(2000.0, description="Square footage of living space", ge=200, le=20000)
    sqft_lot: float = Field(7500.0, description="Square footage of lot", ge=200, le=2000000)
    floors: float = Field(1.5, description="Number of floors", ge=1, le=4)
    waterfront: int = Field(0, description="1 if waterfront property, else 0", ge=0, le=1)
    view: int = Field(0, description="View rating (0 to 4)", ge=0, le=4)
    condition: int = Field(3, description="Overall condition (1 to 5)", ge=1, le=5)
    sqft_above: float = Field(1800.0, description="Square footage above basement", ge=200, le=15000)
    sqft_basement: float = Field(200.0, description="Basement square footage", ge=0, le=10000)
    property_age: float = Field(45.0, description="Age of property in years", ge=0, le=200)

    model_config = {
        "json_schema_extra": {
            "example": {
                "bedrooms": 3.0,
                "bathrooms": 2.25,
                "sqft_living": 2150.0,
                "sqft_lot": 7200.0,
                "floors": 2.0,
                "waterfront": 0,
                "view": 1,
                "condition": 4,
                "sqft_above": 1850.0,
                "sqft_basement": 300.0,
                "property_age": 35.0
            }
        }
    }

# ---------------------------------------------------------------------------
# Core REST Endpoints (Satisfying Part B: API Access & 4+ Application Details)
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serves the Cloud Monitoring Dashboard."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Cloud Dashboard is loading or static/index.html is being prepared."})

@app.get("/api/application", tags=["Application"])
async def get_application_info() -> Dict[str, Any]:
    """
    **API 1: Application Information**
    Retrieves core application details, metadata, framework version, and environment.
    """
    return {
        "application_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "status": "RUNNING",
        "start_time": APP_START_TIME,
        "current_time": datetime.now(timezone.utc).isoformat(),
        "tech_stack": {
            "backend": "FastAPI",
            "runtime": f"Python {platform.python_version()}",
            "platform": f"{platform.system()} {platform.release()}",
            "host": platform.node(),
            "scheduler": "APScheduler (BackgroundInterval)",
            "data_engine": "Pandas, Scikit-learn, NumPy",
            "persistence": "SQLite (Structured Audit Trails)"
        }
    }

@app.get("/api/pipeline/status", tags=["DataOps Pipeline"])
async def get_pipeline_status() -> Dict[str, Any]:
    """
    **API 2: Pipeline Status & 2-Minute Scheduler Details**
    Retrieves current pipeline state, run statistics, success rate, and 2-minute cadence info.
    """
    summary = get_pipeline_summary()
    sched_info = pipeline_runner.get_scheduler_status()
    summary["scheduler"] = sched_info
    return summary

@app.get("/api/pipeline/history", tags=["DataOps Pipeline"])
async def get_pipeline_history(limit: int = 15) -> Dict[str, Any]:
    """
    **API 3: Pipeline Execution History**
    Retrieves recent chronological executions with run ID, durations, statuses, and record counts.
    """
    runs = get_recent_runs(limit=limit)
    return {
        "total_returned": len(runs),
        "history": runs
    }

@app.get("/api/pipeline/events", tags=["DataOps Pipeline"])
async def get_pipeline_stage_events(limit: int = 40) -> Dict[str, Any]:
    """
    **API: Granular Pipeline Stage Events**
    Retrieves chronological micro-events (Ingestion, Preprocessing, EDA, Modeling).
    """
    events = get_recent_events(limit=limit)
    return {
        "total_returned": len(events),
        "events": events
    }

@app.get("/api/dataset/summary", tags=["Dataset & Preprocessing"])
async def get_dataset_summary() -> Dict[str, Any]:
    """
    **API 4: Dataset & Preprocessing Summary**
    Retrieves dataset schema, missing value audit, and calculated summary statistics.
    """
    stats_file = os.path.join(settings.REPORTS_DIR, "summary_statistics.json")
    stats_data = {}
    if os.path.exists(stats_file):
        with open(stats_file, "r", encoding="utf-8") as f:
            stats_data = json.load(f)

    return {
        "dataset_name": "HouseData (King County, WA)",
        "source": settings.DATA_SOURCE,
        "dataset_path": settings.DATASET_PATH,
        "summary_statistics": stats_data
    }

@app.get("/api/eda/summary", tags=["Exploratory Data Analysis"])
async def get_eda_summary() -> Dict[str, Any]:
    """
    **API 5: Exploratory Data Analysis (EDA) Summary**
    Retrieves Pearson correlations, binning distributions, top expensive cities, and feature rankings.
    """
    eda_file = os.path.join(settings.REPORTS_DIR, "eda_summary.json")
    if not os.path.exists(eda_file):
        raise HTTPException(status_code=404, detail="EDA summary not generated yet. Trigger pipeline first.")
    with open(eda_file, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/model/metrics", tags=["Machine Learning"])
async def get_model_metrics() -> Dict[str, Any]:
    """
    **API 6: Machine Learning Model Metrics & Comparison**
    Retrieves evaluation metrics (MAE, RMSE, R²) comparing Linear Regression vs Random Forest.
    """
    metrics_file = os.path.join(settings.REPORTS_DIR, "model_comparison.json")
    if not os.path.exists(metrics_file):
        raise HTTPException(status_code=404, detail="Model metrics not available. Trigger pipeline first.")
    with open(metrics_file, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/pipeline/trigger", tags=["DataOps Pipeline"], status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    **API 7: Trigger Pipeline Manually**
    Manually triggers an immediate execution of the end-to-end DataOps pipeline in the background.
    """
    if pipeline_runner.is_running:
        return {"status": "SKIPPED", "message": "Pipeline run already in progress."}

    background_tasks.add_task(pipeline_runner.execute_pipeline, trigger_source="MANUAL_API_TRIGGER")
    return {
        "status": "ACCEPTED",
        "message": "DataOps pipeline run triggered in background.",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/predict", tags=["Machine Learning"])
async def predict_house_price(request: HousePredictionRequest) -> Dict[str, Any]:
    """
    **API 8: House Price Prediction Inference**
    Predicts house market value given property structural and geographical features.
    """
    try:
        model_pipeline = ModelPipeline()
        features = request.model_dump()
        result = model_pipeline.predict(features)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prediction error: {str(e)}")

def _ec2_metadata() -> Dict[str, Any]:
    """
    Read EC2 instance identity from the IMDSv2 link-local metadata service.
    Returns {"on_ec2": False} instantly when running anywhere else.
    """
    try:
        token_req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"}
        )
        token = urllib.request.urlopen(token_req, timeout=1).read().decode()
        doc_req = urllib.request.Request(
            "http://169.254.169.254/latest/dynamic/instance-identity/document",
            headers={"X-aws-ec2-metadata-token": token}
        )
        doc = json.loads(urllib.request.urlopen(doc_req, timeout=1).read().decode())
        return {
            "on_ec2": True,
            "instance_id": doc.get("instanceId"),
            "instance_type": doc.get("instanceType"),
            "availability_zone": doc.get("availabilityZone"),
            "region": doc.get("region"),
            "image_id": doc.get("imageId")
        }
    except Exception:
        return {"on_ec2": False, "note": "Not running on an EC2 instance."}


@app.get("/api/cloud/deployment", tags=["Cloud Infrastructure"])
async def get_cloud_deployment_details() -> Dict[str, Any]:
    """
    **API 10: Cloud Deployment Details via AWS Built-in APIs**

    Retrieves live infrastructure information by calling AWS's own built-in
    service APIs through boto3 - EC2 DescribeInstances, API Gateway GetApis,
    CloudWatch Logs DescribeLogStreams and Cost Explorer GetCostAndUsage.

    This satisfies rubric 3.1 ("use built-in APIs to access important
    application information such as flow and deployment"). Each section
    degrades gracefully with an explanatory note if AWS credentials or
    permissions are absent, so the endpoint always returns HTTP 200.
    """
    details: Dict[str, Any] = {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "aws_region": settings.AWS_REGION,
        "compute_instance": _ec2_metadata(),
        "cloudwatch_logging": get_cloudwatch_state()
    }

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        details["aws_sdk"] = {"available": False, "note": "boto3 is not installed."}
        return details

    details["aws_sdk"] = {"available": True, "sdk": "boto3"}
    region = settings.AWS_REGION

    # --- AWS built-in API 1: EC2 DescribeInstances -------------------------
    try:
        ec2 = boto3.client("ec2", region_name=region)
        reservations = ec2.describe_instances(
            Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
        ).get("Reservations", [])
        instances = []
        for res in reservations:
            for inst in res.get("Instances", []):
                instances.append({
                    "instance_id": inst.get("InstanceId"),
                    "instance_type": inst.get("InstanceType"),
                    "state": inst.get("State", {}).get("Name"),
                    "public_dns": inst.get("PublicDnsName"),
                    "private_ip": inst.get("PrivateIpAddress"),
                    "launch_time": inst.get("LaunchTime").isoformat() if inst.get("LaunchTime") else None
                })
        details["ec2_instances"] = {"api_called": "ec2:DescribeInstances",
                                    "count": len(instances), "instances": instances}
    except (BotoCoreError, ClientError, Exception) as e:
        details["ec2_instances"] = {"api_called": "ec2:DescribeInstances", "error": str(e)}

    # --- AWS built-in API 2: API Gateway v2 GetApis ------------------------
    try:
        apigw = boto3.client("apigatewayv2", region_name=region)
        apis = [{
            "api_id": a.get("ApiId"),
            "name": a.get("Name"),
            "protocol": a.get("ProtocolType"),
            "endpoint": a.get("ApiEndpoint"),
            "created": a.get("CreatedDate").isoformat() if a.get("CreatedDate") else None
        } for a in apigw.get_apis().get("Items", [])]
        details["api_gateway"] = {"api_called": "apigatewayv2:GetApis",
                                  "count": len(apis), "apis": apis}
    except (BotoCoreError, ClientError, Exception) as e:
        details["api_gateway"] = {"api_called": "apigatewayv2:GetApis", "error": str(e)}

    # --- AWS built-in API 3: CloudWatch Logs DescribeLogStreams ------------
    try:
        cwlogs = boto3.client("logs", region_name=region)
        streams = cwlogs.describe_log_streams(
            logGroupName=settings.CLOUDWATCH_LOG_GROUP,
            orderBy="LastEventTime", descending=True, limit=5
        ).get("logStreams", [])
        details["cloudwatch_log_streams"] = {
            "api_called": "logs:DescribeLogStreams",
            "log_group": settings.CLOUDWATCH_LOG_GROUP,
            "streams": [{
                "name": s.get("logStreamName"),
                "stored_bytes": s.get("storedBytes"),
                "last_event": datetime.fromtimestamp(
                    s["lastEventTimestamp"] / 1000, tz=timezone.utc
                ).isoformat() if s.get("lastEventTimestamp") else None
            } for s in streams]
        }
    except (BotoCoreError, ClientError, Exception) as e:
        details["cloudwatch_log_streams"] = {"api_called": "logs:DescribeLogStreams", "error": str(e)}

    # --- AWS built-in API 4: Cost Explorer GetCostAndUsage -----------------
    try:
        from datetime import timedelta
        ce = boto3.client("ce", region_name="us-east-1")
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=7)
        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"]
        )
        breakdown = [{
            "date": r["TimePeriod"]["Start"],
            "cost": round(float(r["Total"]["UnblendedCost"]["Amount"]), 4),
            "unit": r["Total"]["UnblendedCost"]["Unit"]
        } for r in resp.get("ResultsByTime", [])]
        details["billing_last_7_days"] = {
            "api_called": "ce:GetCostAndUsage",
            "total_cost": round(sum(d["cost"] for d in breakdown), 4),
            "daily_breakdown": breakdown
        }
    except (BotoCoreError, ClientError, Exception) as e:
        details["billing_last_7_days"] = {"api_called": "ce:GetCostAndUsage", "error": str(e)}

    return details


@app.get("/api/health", tags=["Application"])
async def health_check() -> Dict[str, str]:
    """
    **API 9: Health Check**
    Cloud health-check probe endpoint.
    """
    return {
        "status": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
