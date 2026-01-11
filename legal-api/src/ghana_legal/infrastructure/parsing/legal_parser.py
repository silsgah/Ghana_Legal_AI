from pathlib import Path
from typing import List

from langchain_core.documents import Document
from loguru import logger


class LegalDocumentLoader:
    """Loads legal documents from the local data directory."""

    def __init__(self, data_dir: str = "data/ghana_legal"):
        self.data_dir = Path(data_dir)

    def load_expert_documents(self, expert_id: str, expert_name: str) -> List[Document]:
        """Load documents relevant to a specific legal expert."""
        docs = []

        # Map expert IDs to subdirectories
        expert_dirs = {
            "constitutional": "constitution",
            "case_law": ["supreme_court", "court_of_appeal"],
            "legal_historian": ["statutes", "history"],  # Assuming history or statutes
        }

        if expert_id not in expert_dirs:
            logger.warning(f"No specific directory mapping for expert {expert_id}")
            return []

        targets = expert_dirs[expert_id]
        if isinstance(targets, str):
            targets = [targets]

        for target in targets:
            target_path = self.data_dir / target
            if not target_path.exists():
                logger.debug(f"Directory {target_path} does not exist, skipping.")
                continue

            # Walk through directory
            for file_path in target_path.rglob("*"):
                if file_path.is_file():
                    try:
                        doc = self._parse_file(file_path)
                        if doc:
                            # Enrich metadata
                            doc.metadata["expert_id"] = expert_id
                            doc.metadata["expert_name"] = expert_name
                            doc.metadata["category"] = target
                            docs.append(doc)
                    except Exception as e:
                        logger.error(f"Failed to parse {file_path}: {e}")

        logger.info(f"Loaded {len(docs)} documents for {expert_name} from local storage.")
        return docs

    def _parse_file(self, file_path: Path) -> Document | None:
        """Parse a single file into a Document."""
        # Simple implementation for .txt files
        if file_path.suffix.lower() == ".txt":
            content = file_path.read_text(encoding="utf-8")
            return Document(
                page_content=content,
                metadata={"source": str(file_path), "filename": file_path.name},
            )
        
        # TODO: Add PDF parsing support (Phase 3)
        if file_path.suffix.lower() == ".pdf":
            logger.warning(f"PDF parsing not yet implemented for {file_path.name}")
            return None

        return None
