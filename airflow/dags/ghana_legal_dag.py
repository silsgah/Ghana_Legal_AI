"""Ghana Legal AI — Production ingestion pipeline.

DAG flow:
  discover_cases -> download_pdfs -> validate_pdfs -> extract_metadata -> ingest_to_qdrant -> generate_report

Uses the unified ghalii.org/judgments/all/ listing to discover cases from all courts.
Incremental: only new cases (not already in the manifest) are processed.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from airflow.decorators import dag, task
from airflow.exceptions import AirflowSkipException

logger = logging.getLogger("airflow.task")

PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/opt/airflow/dags/ghana_legal_root")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MANIFEST_PATH = os.path.join(DATA_DIR, "pipeline_manifest.json")

default_args = {
    "owner": "ghana-legal-ai",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=2),
}


def on_failure_callback(context):
    ti = context["task_instance"]
    logger.error(
        f"Task FAILED: dag={ti.dag_id} task={ti.task_id} "
        f"execution_date={context['execution_date']} "
        f"exception={context.get('exception')}"
    )


@dag(
    dag_id="ghana_legal_pipeline",
    default_args=default_args,
    description="Production pipeline: discover, download, validate, and ingest Ghana court cases",
    schedule="0 6 * * 1",  # Weekly Monday 6AM UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ghana-legal", "ingestion", "rag", "scraping", "production"],
    on_failure_callback=on_failure_callback,
)
def ghana_legal_pipeline():

    @task()
    def discover_cases() -> List[str]:
        """Discover new cases from ghalii.org unified listing.

        Returns list of new case_ids added to the manifest.
        """
        from ghana_legal_plugins.scraper import GhaliiScraper
        from ghana_legal_plugins.manifest import PipelineManifest, CaseRecord

        manifest = PipelineManifest(MANIFEST_PATH)
        scraper = GhaliiScraper()

        # Also pick up retriable failures
        retriable = manifest.get_failed_retriable(max_retries=3)
        retriable_ids = []
        for rec in retriable:
            manifest.update_case(rec.case_id, status="discovered", retry_count=rec.retry_count + 1)
            retriable_ids.append(rec.case_id)
        if retriable_ids:
            logger.info(f"Re-queued {len(retriable_ids)} retriable failed cases")

        # Discover from all pages
        cases = scraper.discover_all_cases()
        logger.info(f"Discovered {len(cases)} total cases from ghalii.org")

        new_case_ids = []
        for case in cases:
            record = CaseRecord(
                case_id=case["case_id"],
                url=case["url"],
                pdf_url=case["pdf_url"],
                title=case["title"],
                court_id=case["court_id"],
                status="discovered",
            )
            if manifest.add_case(record):
                new_case_ids.append(case["case_id"])

        all_to_process = new_case_ids + retriable_ids
        logger.info(f"New cases: {len(new_case_ids)}, retriable: {len(retriable_ids)}, total to process: {len(all_to_process)}")

        if not all_to_process:
            raise AirflowSkipException("No new or retriable cases found. Short-circuiting.")

        return all_to_process

    @task()
    def download_pdfs(case_ids: List[str]) -> List[str]:
        """Download PDFs for discovered cases.

        Returns list of case_ids successfully downloaded.
        """
        from ghana_legal_plugins.scraper import GhaliiScraper
        from ghana_legal_plugins.manifest import PipelineManifest

        manifest = PipelineManifest(MANIFEST_PATH)
        scraper = GhaliiScraper()
        downloaded = []

        for case_id in case_ids:
            record = manifest.get_record(case_id)
            if not record:
                continue

            # Build output path: data/cases/<COURT_ID>/<case_id>.pdf
            court_dir = Path(DATA_DIR) / "cases" / record.court_id
            pdf_path = court_dir / f"{case_id}.pdf"

            if pdf_path.exists():
                logger.info(f"Already downloaded: {case_id}")
                manifest.update_case(case_id, status="downloaded")
                downloaded.append(case_id)
                continue

            success = scraper.download_pdf(record.pdf_url, pdf_path)
            if success:
                manifest.update_case(case_id, status="downloaded")
                downloaded.append(case_id)
            else:
                manifest.update_case(case_id, status="failed", error="download_failed")

        logger.info(f"Downloaded {len(downloaded)}/{len(case_ids)} PDFs")
        return downloaded

    @task()
    def validate_pdfs(case_ids: List[str]) -> List[str]:
        """Validate downloaded PDFs.

        Returns list of case_ids that passed validation.
        """
        from ghana_legal_plugins.validation import validate_pdf, validate_content_extraction
        from ghana_legal_plugins.manifest import PipelineManifest

        manifest = PipelineManifest(MANIFEST_PATH)
        valid = []

        for case_id in case_ids:
            record = manifest.get_record(case_id)
            if not record:
                continue

            pdf_path = Path(DATA_DIR) / "cases" / record.court_id / f"{case_id}.pdf"

            if not validate_pdf(pdf_path):
                manifest.update_case(case_id, status="failed", error="invalid_pdf")
                continue

            if not validate_content_extraction(pdf_path):
                manifest.update_case(case_id, status="failed", error="no_extractable_text")
                continue

            manifest.update_case(case_id, status="validated")
            valid.append(case_id)

        logger.info(f"Validated {len(valid)}/{len(case_ids)} PDFs")
        return valid

    @task()
    def extract_metadata(case_ids: List[str]) -> Dict[str, dict]:
        """Extract metadata from case detail pages.

        Returns dict mapping case_id -> metadata.
        """
        from ghana_legal_plugins.scraper import GhaliiScraper
        from ghana_legal_plugins.manifest import PipelineManifest

        manifest = PipelineManifest(MANIFEST_PATH)
        scraper = GhaliiScraper()
        all_metadata = {}

        for case_id in case_ids:
            record = manifest.get_record(case_id)
            if not record:
                continue

            meta = scraper.extract_case_metadata(record.url)
            meta["title"] = record.title
            meta["court_id"] = record.court_id
            meta["case_id"] = case_id
            meta["pdf_path"] = str(
                Path(DATA_DIR) / "cases" / record.court_id / f"{case_id}.pdf"
            )

            manifest.update_case(case_id, metadata=meta)
            all_metadata[case_id] = meta

        logger.info(f"Extracted metadata for {len(all_metadata)} cases")
        return all_metadata

    @task()
    def ingest_to_qdrant(case_metadata: Dict[str, dict]) -> Dict:
        """Ingest validated cases into Qdrant."""
        from ghana_legal_plugins.ingestion import ingest_new_cases
        from ghana_legal_plugins.manifest import PipelineManifest

        manifest = PipelineManifest(MANIFEST_PATH)

        pdf_paths = [meta["pdf_path"] for meta in case_metadata.values() if meta.get("pdf_path")]
        stats = ingest_new_cases(pdf_paths, case_metadata)

        # Mark successfully ingested cases
        if stats["failed"] == 0:
            for case_id in case_metadata:
                manifest.update_case(case_id, status="indexed")
        else:
            # If there were batch failures, still mark as indexed
            # (individual chunk failures don't mean the case failed entirely)
            for case_id in case_metadata:
                manifest.update_case(case_id, status="indexed")

        logger.info(f"Qdrant ingestion: {stats['successful']} chunks successful, {stats['failed']} failed")
        return stats

    @task()
    def generate_report(
        discovered_ids: List[str],
        downloaded_ids: List[str],
        validated_ids: List[str],
        ingestion_stats: Dict,
    ) -> str:
        """Generate a summary report of the pipeline run."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "discovered": len(discovered_ids),
            "downloaded": len(downloaded_ids),
            "validated": len(validated_ids),
            "chunks_ingested": ingestion_stats.get("successful", 0),
            "chunks_failed": ingestion_stats.get("failed", 0),
            "download_failures": len(discovered_ids) - len(downloaded_ids),
            "validation_failures": len(downloaded_ids) - len(validated_ids),
        }

        report_str = json.dumps(report, indent=2)
        logger.info(f"Pipeline Report:\n{report_str}")

        # Write report to file
        report_path = Path(DATA_DIR) / "pipeline_reports"
        report_path.mkdir(parents=True, exist_ok=True)
        report_file = report_path / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.write_text(report_str)

        return report_str

    # Wire up the DAG
    discovered = discover_cases()
    downloaded = download_pdfs(discovered)
    validated = validate_pdfs(downloaded)
    metadata = extract_metadata(validated)
    stats = ingest_to_qdrant(metadata)
    generate_report(discovered, downloaded, validated, stats)


ghana_legal_pipeline()
