
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# Add plugins to path to import local modules
current_file = Path(__file__).resolve()
plugins_dir = current_file.parents[1] / "plugins"
if str(plugins_dir) not in sys.path:
    sys.path.append(str(plugins_dir))

from ghana_legal.fetching import fetch_new_cases
from ghana_legal.indexing import index_new_cases

# Default DAG arguments
default_args = {
    "owner": "ghana-legal-ai",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1), # Start form beginning of year, catchup=False handles skipping
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "catchup": False,
}

# Define Paths
# Assuming DAG runs in project root context or airflow home
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai")
CASES_DIR = os.path.join(PROJECT_ROOT, "data/cases")

# Create the DAG
dag = DAG(
    "ghana_legal_pipeline",
    default_args=default_args,
    description="Automated pipeline: Fetch new Ghana Supreme Court cases -> Index into Vector DB",
    schedule="0 6 * * *",  # Daily at 6 AM
    max_active_runs=1,
    catchup=False,
    tags=["ghana-legal", "ingestion", "rag", "scraping"],
)

def _setup_directories():
    """Ensure data directories exist"""
    Path(CASES_DIR).mkdir(parents=True, exist_ok=True)
    print(f"Verified directory: {CASES_DIR}")

def _fetch_cases(**context):
    """Wrapper to call fetch logic with specific output dir"""
    new_files = fetch_new_cases(output_dir=CASES_DIR, limit=10)
    # Push metadata to XCom for reporting if needed
    context['ti'].xcom_push(key='new_files_count', value=len(new_files))
    if not new_files:
        print("No new files found.")
    return len(new_files)

def _generate_report(**context):
    """Log summary of operation"""
    ti = context['ti']
    count = ti.xcom_pull(task_ids='fetch_new_cases', key='new_files_count')
    print(f"✅ Daily Report: Successfully ingested {count} new cases into the Knowledge Base.")

# Task Definitions

setup_task = PythonOperator(
    task_id="setup_directories",
    python_callable=_setup_directories,
    dag=dag,
)

fetch_task = PythonOperator(
    task_id="fetch_new_cases",
    python_callable=_fetch_cases,
    provide_context=True,
    dag=dag,
)

index_task = PythonOperator(
    task_id="ingest_vector_db",
    python_callable=index_new_cases,
    dag=dag,
)

report_task = PythonOperator(
    task_id="generate_report",
    python_callable=_generate_report,
    provide_context=True,
    dag=dag,
)

# Task Dependencies
setup_task >> fetch_task >> index_task >> report_task
