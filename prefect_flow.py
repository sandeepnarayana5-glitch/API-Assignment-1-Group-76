"""
Prefect flow for the house price prediction DataOps pipeline.

Each stage of the existing pipeline becomes a Prefect task, so Prefect Cloud
records the timing, status and logs of every stage separately rather than
treating the whole run as one opaque block. The flow itself is scheduled every
two minutes by the deployment defined in prefect.yaml.

The same pipeline modules used by the FastAPI application are reused verbatim -
nothing is reimplemented here, this file only orchestrates them.
"""

import time
import uuid
from datetime import datetime, timezone

from prefect import flow, task, get_run_logger
from prefect.artifacts import create_markdown_artifact

from pipeline.logger import PipelineLogger
from pipeline.ingestion import DataIngestion
from pipeline.preprocessing import DataPreprocessing
from pipeline.eda import ExploratoryDataAnalysis
from pipeline.model import ModelPipeline


@task(name="Ingest raw data", retries=1, retry_delay_seconds=10)
def ingest_task(run_id: str):
    """Load the Kaggle house sales file and apply the data quality simulation."""
    logger = get_run_logger()
    pipeline_logger = PipelineLogger(run_id)

    df_raw, meta = DataIngestion(logger=pipeline_logger).ingest_data()

    logger.info(f"Loaded {meta['rows']} rows and {meta['columns']} columns from {meta['source']}")
    if meta.get("simulated_nulls"):
        logger.info(
            f"Injected {sum(meta['simulated_nulls'].values())} null cells across "
            f"{len(meta['simulated_nulls'])} numeric columns so the imputation step is exercised"
        )
    return df_raw, meta


@task(name="Clean and normalise", retries=1, retry_delay_seconds=10)
def preprocess_task(run_id: str, df_raw):
    """Impute missing values, drop invalid rows and outliers, scale features."""
    logger = get_run_logger()
    pipeline_logger = PipelineLogger(run_id)

    df_clean, meta = DataPreprocessing(logger=pipeline_logger).process(df_raw)

    logger.info(f"Removed {meta['zero_prices_removed']} rows with a zero sale price")
    logger.info(
        f"Removed {meta['outliers_removed']} luxury outliers above "
        f"${meta['outlier_threshold_price']:,.0f}"
    )
    for entry in meta.get("imputation_log", []):
        logger.info(f"Imputation: {entry}")
    logger.info(f"Clean dataset contains {len(df_clean)} records")
    return df_clean, meta


@task(name="Exploratory data analysis", retries=1, retry_delay_seconds=10)
def eda_task(run_id: str, df_clean):
    """Correlations, binning, four encoding techniques, charts, feature importance."""
    logger = get_run_logger()
    pipeline_logger = PipelineLogger(run_id)

    df_eda, meta = ExploratoryDataAnalysis(logger=pipeline_logger).analyze(df_clean)

    for name, detail in meta.get("encoding_summary", {}).items():
        logger.info(f"Encoding applied - {detail['technique']} on '{detail['source_column']}'")
    top = meta["feature_importance_ranking"][0]
    logger.info(f"Strongest predictor: {top['feature']} at {top['importance']:.1%}")
    return df_eda, meta


@task(name="Train and compare models", retries=1, retry_delay_seconds=10)
def model_task(run_id: str, df_clean):
    """Fit the linear baseline and the random forest, then select on test R2."""
    logger = get_run_logger()
    pipeline_logger = PipelineLogger(run_id)

    _, meta = ModelPipeline(logger=pipeline_logger).train_and_evaluate(df_clean)

    base, imp = meta["baseline_model"], meta["improved_model"]
    logger.info(f"Baseline {base['name']}: R2={base['r2']}, MAE=${base['mae']:,.0f}")
    logger.info(f"Improved {imp['name']}: R2={imp['r2']}, MAE=${imp['mae']:,.0f}")
    logger.info(f"Selected: {meta['selected_model']}")
    return meta


@flow(name="House Price DataOps Pipeline", log_prints=True)
def house_price_pipeline():
    """
    End to end run: ingest, clean, analyse, model.

    Scheduled every two minutes by the deployment. Each run publishes a summary
    artifact to Prefect Cloud so the dashboard shows the outcome without anyone
    needing to open the logs.
    """
    logger = get_run_logger()
    started = time.time()
    run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    logger.info(f"Starting pipeline run {run_id}")

    df_raw, ingest_meta = ingest_task(run_id)
    df_clean, prep_meta = preprocess_task(run_id, df_raw)
    _, eda_meta = eda_task(run_id, df_clean)
    model_meta = model_task(run_id, df_clean)

    duration = time.time() - started
    selected = model_meta["selected_metrics"]
    top_feature = eda_meta["feature_importance_ranking"][0]

    summary = f"""# Pipeline run {run_id}

Completed in **{duration:.1f} seconds**.

## Data
| Stage | Result |
|---|---|
| Rows ingested | {ingest_meta['rows']:,} |
| Null cells injected for imputation | {ingest_meta.get('null_cells_total', 0):,} |
| Zero-price rows removed | {prep_meta['zero_prices_removed']} |
| Luxury outliers removed | {prep_meta['outliers_removed']} |
| Rows used for training | {len(df_clean):,} |

## Analysis
| Item | Result |
|---|---|
| Encoding techniques applied | {len(eda_meta.get('encoding_summary', {}))} |
| Strongest predictor | {top_feature['feature']} ({top_feature['importance']:.1%}) |
| Charts generated | {len(eda_meta.get('charts_generated', []))} |

## Model
| Model | R2 | MAE |
|---|---|---|
| {model_meta['baseline_model']['name']} | {model_meta['baseline_model']['r2']} | ${model_meta['baseline_model']['mae']:,.0f} |
| {model_meta['improved_model']['name']} | {model_meta['improved_model']['r2']} | ${model_meta['improved_model']['mae']:,.0f} |

**Selected: {model_meta['selected_model']}** — R2 {selected['r2']}, MAE ${selected['mae']:,.0f}
"""

    create_markdown_artifact(
        key="pipeline-run-summary",
        markdown=summary,
        description=f"Summary for {run_id}"
    )

    logger.info(f"Pipeline run {run_id} finished in {duration:.1f}s")

    return {
        "run_id": run_id,
        "status": "SUCCESS",
        "duration_seconds": round(duration, 2),
        "records_processed": len(df_clean),
        "selected_model": model_meta["selected_model"],
        "r2": selected["r2"],
    }


if __name__ == "__main__":
    house_price_pipeline()
