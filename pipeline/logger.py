import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.settings import settings

# Setup standard logger
logger = logging.getLogger("DataOpsPipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Console handler
    c_handler = logging.StreamHandler()
    c_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File handler for plain text
    log_file = os.path.join(settings.LOGS_DIR, "pipeline.log")
    f_handler = logging.FileHandler(log_file, encoding="utf-8")
    f_handler.setFormatter(c_format)
    logger.addHandler(f_handler)

# Structured JSON log file
JSON_LOG_FILE = os.path.join(settings.LOGS_DIR, "pipeline_structured.jsonl")

# ---------------------------------------------------------------------------
# Optional AWS CloudWatch Logs emitter.
# When CLOUDWATCH_ENABLED=true and boto3 credentials are present, every pipeline
# event is also shipped to a CloudWatch Log Group so the run history is visible
# on a real cloud dashboard. Every call is defensive: if boto3 is missing or the
# instance has no permissions, the pipeline continues on local logging alone.
# ---------------------------------------------------------------------------
_cw_client = None
_cw_stream = None
_cw_state = {"enabled": False, "reason": "disabled in settings"}

def _cloudwatch():
    """Lazily create the CloudWatch Logs client and log stream."""
    global _cw_client, _cw_stream
    if not settings.CLOUDWATCH_ENABLED:
        return None, None
    if _cw_client is not None:
        return _cw_client, _cw_stream
    try:
        import boto3
        client = boto3.client("logs", region_name=settings.AWS_REGION)
        group = settings.CLOUDWATCH_LOG_GROUP
        stream = "pipeline-" + datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            client.create_log_group(logGroupName=group)
        except client.exceptions.ResourceAlreadyExistsException:
            pass
        try:
            client.create_log_stream(logGroupName=group, logStreamName=stream)
        except client.exceptions.ResourceAlreadyExistsException:
            pass
        _cw_client, _cw_stream = client, stream
        _cw_state.update({"enabled": True, "reason": "connected",
                          "log_group": group, "log_stream": stream})
        logger.info(f"CloudWatch logging active -> {group}/{stream}")
    except Exception as e:
        _cw_state.update({"enabled": False, "reason": f"unavailable: {e}"})
        logger.warning(f"CloudWatch logging unavailable, using local logs only: {e}")
        settings.CLOUDWATCH_ENABLED = False
        return None, None
    return _cw_client, _cw_stream

def _emit_cloudwatch(entry: Dict[str, Any]):
    """Ship one structured event to CloudWatch Logs (best effort)."""
    client, stream = _cloudwatch()
    if not client:
        return
    try:
        client.put_log_events(
            logGroupName=settings.CLOUDWATCH_LOG_GROUP,
            logStreamName=stream,
            logEvents=[{
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "message": json.dumps(entry)
            }]
        )
    except Exception as e:
        logger.warning(f"CloudWatch put_log_events failed: {e}")

def get_cloudwatch_state() -> Dict[str, Any]:
    """Expose CloudWatch connection state for the /api/cloud/deployment endpoint."""
    if settings.CLOUDWATCH_ENABLED and _cw_client is None:
        _cloudwatch()
    return dict(_cw_state)

def init_db():
    """Initialize SQLite tables for pipeline runs and stage events."""
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    
    # Table for full pipeline runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL,
            duration_seconds REAL,
            records_processed INTEGER,
            metrics_json TEXT,
            error_message TEXT
        )
    """)
    
    # Table for granular stage events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            stage TEXT NOT NULL,
            event TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_seconds REAL,
            message TEXT,
            FOREIGN KEY (run_id) REFERENCES pipeline_runs (run_id)
        )
    """)
    
    conn.commit()
    conn.close()

# Initialize DB on import
init_db()

class PipelineLogger:
    """Manages structured JSON logging and SQLite state persistence."""
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.start_time = datetime.now(timezone.utc).isoformat()
        
    def start_run(self):
        """Record the start of a pipeline run."""
        conn = sqlite3.connect(settings.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO pipeline_runs (run_id, start_time, status) VALUES (?, ?, ?)",
            (self.run_id, self.start_time, "RUNNING")
        )
        conn.commit()
        conn.close()
        self.log_event("Pipeline", "Pipeline Started", "RUNNING", message="Workflow triggered")

    def log_event(self, stage: str, event: str, status: str, duration: float = 0.0, message: str = "", details: Optional[Dict[str, Any]] = None):
        """Log a granular stage event to console, JSONL file, and SQLite."""
        now_str = datetime.now(timezone.utc).isoformat()
        log_entry = {
            "timestamp": now_str,
            "run_id": self.run_id,
            "stage": stage,
            "event": event,
            "status": status,
            "duration_seconds": round(duration, 3),
            "message": message,
            "details": details or {}
        }
        
        # Write to JSONL
        with open(JSON_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Ship to AWS CloudWatch Logs (no-op when disabled or unavailable)
        _emit_cloudwatch(log_entry)
            
        # Write to SQLite
        try:
            conn = sqlite3.connect(settings.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pipeline_events 
                (run_id, timestamp, stage, event, status, duration_seconds, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (self.run_id, now_str, stage, event, status, duration, message)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error persisting event to DB: {e}")
            
        # Log to standard logger
        lvl = logging.INFO if status != "FAILED" else logging.ERROR
        logger.log(lvl, f"[{self.run_id}] [{stage}] {event} - {status}: {message}")

    def complete_run(self, status: str, records: int = 0, metrics: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """Finalize pipeline run record."""
        end_time = datetime.now(timezone.utc).isoformat()
        start_dt = datetime.fromisoformat(self.start_time)
        end_dt = datetime.fromisoformat(end_time)
        duration = (end_dt - start_dt).total_seconds()
        
        conn = sqlite3.connect(settings.DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE pipeline_runs
            SET end_time = ?, status = ?, duration_seconds = ?, records_processed = ?, metrics_json = ?, error_message = ?
            WHERE run_id = ?
            """,
            (end_time, status, round(duration, 2), records, json.dumps(metrics or {}), error, self.run_id)
        )
        conn.commit()
        conn.close()
        
        self.log_event(
            "Pipeline",
            "Pipeline Completed",
            status,
            duration=duration,
            message=f"Pipeline finished with status {status}" if not error else f"Failed: {error}"
        )

def reconcile_stale_runs() -> int:
    """
    Mark runs left in RUNNING state by a crash or restart as FAILED.

    Without this, a process killed mid-pipeline leaves an orphan RUNNING row
    forever: the dashboard reports "RUNNING" permanently and the success rate
    is permanently wrong. Called once on application startup.
    """
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pipeline_runs WHERE status = 'RUNNING'")
    stale = cursor.fetchone()[0]
    if stale:
        cursor.execute(
            """
            UPDATE pipeline_runs
            SET status = 'FAILED',
                end_time = ?,
                error_message = 'Run interrupted by application restart (auto-reconciled on startup)'
            WHERE status = 'RUNNING'
            """,
            (datetime.now(timezone.utc).isoformat(),)
        )
        conn.commit()
        logger.warning(f"Reconciled {stale} stale RUNNING pipeline run(s) to FAILED on startup.")
    conn.close()
    return stale

# Query Helper Functions for Dashboard and REST APIs
def get_pipeline_summary() -> Dict[str, Any]:
    """Retrieve high-level pipeline status and run statistics."""
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM pipeline_runs")
    total_runs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM pipeline_runs WHERE status = 'SUCCESS'")
    successful_runs = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM pipeline_runs WHERE status = 'FAILED'")
    failed_runs = cursor.fetchone()[0]
    
    cursor.execute("SELECT AVG(duration_seconds) FROM pipeline_runs WHERE status = 'SUCCESS'")
    avg_duration_row = cursor.fetchone()[0]
    avg_duration = round(avg_duration_row, 2) if avg_duration_row else 0.0
    
    cursor.execute("SELECT * FROM pipeline_runs ORDER BY start_time DESC LIMIT 1")
    latest_run = cursor.fetchone()
    
    conn.close()
    
    latest_dict = dict(latest_run) if latest_run else None
    if latest_dict and isinstance(latest_dict.get("metrics_json"), str):
        try:
            latest_dict["metrics"] = json.loads(latest_dict.pop("metrics_json"))
        except (json.JSONDecodeError, TypeError):
            latest_dict["metrics"] = {}
            latest_dict.pop("metrics_json", None)

    current_status = "IDLE"
    if latest_dict and latest_dict.get("status") == "RUNNING":
        current_status = "RUNNING"
    elif latest_dict:
        current_status = latest_dict.get("status")
        
    return {
        "current_status": current_status,
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "success_rate": round((successful_runs / total_runs * 100), 1) if total_runs > 0 else 100.0,
        "average_duration_seconds": avg_duration,
        "latest_run": latest_dict,
        "scheduler_interval_seconds": settings.SCHEDULER_INTERVAL_SECONDS
    }

def get_recent_runs(limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieve recent pipeline executions."""
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pipeline_runs ORDER BY start_time DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get("metrics_json"), str):
            try:
                r["metrics"] = json.loads(r.pop("metrics_json"))
            except (json.JSONDecodeError, TypeError):
                r["metrics"] = {}
                r.pop("metrics_json", None)
        result.append(r)
    return result

def get_recent_events(limit: int = 40) -> List[Dict[str, Any]]:
    """Retrieve recent granular events."""
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pipeline_events ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
