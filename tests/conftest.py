"""
Shared pytest setup.

The API tests read the JSON artifacts produced by the pipeline (summary
statistics, EDA summary, model comparison) and the serialised model file. On a
clean checkout none of those exist yet, so the suite used to depend on artifacts
left behind by an earlier manual run. This fixture executes the pipeline exactly
once per test session, making the whole suite reproducible from a fresh clone.
"""
import pytest

from pipeline.runner import pipeline_runner
from pipeline.logger import get_pipeline_summary


@pytest.fixture(scope="session", autouse=True)
def bootstrap_pipeline():
    """Guarantee one completed pipeline run before any test executes."""
    summary = get_pipeline_summary()
    if summary["total_runs"] == 0:
        result = pipeline_runner.execute_pipeline(trigger_source="PYTEST_BOOTSTRAP")
        assert result["status"] == "SUCCESS", f"Bootstrap run failed: {result.get('error')}"
    yield
