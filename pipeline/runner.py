import os
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config.settings import settings
from pipeline.logger import PipelineLogger
from pipeline.ingestion import DataIngestion
from pipeline.preprocessing import DataPreprocessing
from pipeline.eda import ExploratoryDataAnalysis
from pipeline.model import ModelPipeline

class PipelineRunner:
    """Orchestrates end-to-end DataOps pipeline runs and manages scheduling."""

    def __init__(self):
        self.scheduler: Optional[BackgroundScheduler] = None
        self.is_running = False

    def execute_pipeline(self, trigger_source: str = "SCHEDULED") -> Dict[str, Any]:
        """
        Executes complete pipeline workflow idempotently:
        Ingestion -> Preprocessing -> EDA -> ML Evaluation -> Logging
        """
        if self.is_running:
            return {"status": "SKIPPED", "message": "Pipeline run already in progress"}

        self.is_running = True
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        logger = PipelineLogger(run_id)
        logger.start_run()
        
        start_time = time.time()
        pipeline_result = {
            "run_id": run_id,
            "trigger_source": trigger_source,
            "status": "RUNNING",
            "start_time": datetime.now(timezone.utc).isoformat()
        }

        try:
            # 1. Ingestion
            ingestion = DataIngestion(logger=logger)
            df_raw, ingestion_meta = ingestion.ingest_data()

            # 2. Preprocessing & Data Quality
            preprocessor = DataPreprocessing(logger=logger)
            df_clean, prep_meta = preprocessor.process(df_raw)

            # 3. Exploratory Data Analysis
            eda = ExploratoryDataAnalysis(logger=logger)
            df_eda, eda_meta = eda.analyze(df_clean)

            # 4. Model Training & Comparison
            model_pipeline = ModelPipeline(logger=logger)
            best_model, model_meta = model_pipeline.train_and_evaluate(df_clean)

            total_duration = time.time() - start_time
            records_count = len(df_clean)

            metrics_summary = {
                "records_processed": records_count,
                "initial_records": len(df_raw),
                "features_analyzed": len(df_clean.columns),
                "top_feature": eda_meta["feature_importance_ranking"][0]["feature"],
                "best_model": model_meta["selected_model"],
                "model_r2": model_meta["selected_metrics"]["r2"],
                "model_mae": model_meta["selected_metrics"]["mae"],
                "encodings_applied": len(eda_meta.get("encoding_summary", {})),
                "nulls_imputed": len(prep_meta.get("imputation_log", []))
            }

            logger.complete_run(
                status="SUCCESS",
                records=records_count,
                metrics=metrics_summary
            )

            pipeline_result.update({
                "status": "SUCCESS",
                "duration_seconds": round(total_duration, 2),
                "records_processed": records_count,
                "metrics": metrics_summary
            })

        except Exception as e:
            total_duration = time.time() - start_time
            err_msg = str(e)
            logger.complete_run(status="FAILED", records=0, error=err_msg)
            pipeline_result.update({
                "status": "FAILED",
                "duration_seconds": round(total_duration, 2),
                "error": err_msg
            })
        finally:
            self.is_running = False

        return pipeline_result

    def start_scheduler(self):
        """Initializes and starts the 2-minute periodic APScheduler."""
        if self.scheduler and self.scheduler.running:
            return

        self.scheduler = BackgroundScheduler(daemon=True)
        interval_secs = settings.SCHEDULER_INTERVAL_SECONDS
        self.scheduler.add_job(
            func=self.execute_pipeline,
            trigger=IntervalTrigger(seconds=interval_secs),
            id="dataops_pipeline_job",
            name="Periodic DataOps Pipeline Job",
            replace_existing=True,
            kwargs={"trigger_source": "SCHEDULED"}
        )
        self.scheduler.start()

    def get_scheduler_status(self) -> Dict[str, Any]:
        """Returns scheduler state and next run timestamp."""
        if not self.scheduler or not self.scheduler.running:
            return {"scheduler_running": False, "next_run_time": None}
            
        job = self.scheduler.get_job("dataops_pipeline_job")
        next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
        return {
            "scheduler_running": True,
            "interval_seconds": settings.SCHEDULER_INTERVAL_SECONDS,
            "next_run_time": next_run
        }

# Global singleton runner
pipeline_runner = PipelineRunner()
