
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Import task functions from plugins structure
# Relies on PYTHONPATH set in docker-compose.yml
from ghana_legal_plugins.fetching import fetch_new_cases
from ghana_legal_plugins.indexing import index_new_cases

# Default DAG arguments
default_args = {
    "owner": "ghana-legal-ai",
    "depends_on_past": False,
    "start_date": datetime(2025, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "catchup": False,
}

# Create the DAG
dag = DAG(
    "ghana_legal_pipeline",
    default_args=default_args,
    description="Automated pipeline: Fetch new Ghana Supreme Court cases -> Index into Vector DB",
    schedule="0 6 * * *",  # Daily at 6 AM UTC
    max_active_runs=1,
    catchup=False,
    tags=["ghana-legal", "ingestion", "rag", "scraping"],
)

# Wrapper to provide arguments to fetching function
def fetch_cases_task(**context):
    # Determine output directory
    import os
    project_root = os.environ.get("PROJECT_ROOT", "/opt/airflow/dags/ghana_legal_root")
    cases_dir = os.path.join(project_root, "data/cases")
    
    # Execute
    new_files = fetch_new_cases(output_dir=cases_dir, limit=10)
    
    # Report
    print(f"Fetched {len(new_files)} new files.")
    context['ti'].xcom_push(key='new_files_count', value=len(new_files))

def generate_report_task(**context):
    ti = context['ti']
    count = ti.xcom_pull(task_ids='fetch_new_cases', key='new_files_count')
    print(f"✅ Daily Report: Successfully ingested {count} new cases into the Knowledge Base.")

# Task definitions
setup_task = PythonOperator(
    task_id="setup_directories",
    python_callable=lambda: print("Setup handled by fetching logic"),
    dag=dag,
)

fetch_task = PythonOperator(
    task_id="fetch_new_cases",
    python_callable=fetch_cases_task,
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
    python_callable=generate_report_task,
    provide_context=True,
    dag=dag,
)

# Task dependencies
setup_task >> fetch_task >> index_task >> report_task
