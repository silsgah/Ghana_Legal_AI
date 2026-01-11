import logging
from typing import Generator

from langchain_community.document_loaders import WebBaseLoader, WikipediaLoader
from langchain_core.documents import Document
from tqdm import tqdm

from ghana_legal.domain.legal_expert import LegalExpert, LegalExpertExtract
from ghana_legal.domain.legal_expert_factory import LegalExpertFactory
from ghana_legal.infrastructure.parsing.legal_parser import LegalDocumentLoader


logger = logging.getLogger(__name__)


def get_extraction_generator(
    experts: list[LegalExpertExtract],
) -> Generator[tuple[LegalExpert, list[Document]], None, None]:
    """Extract documents for a list of legal experts, yielding one at a time.

    Args:
        experts: A list of LegalExpertExtract objects containing expert information.

    Yields:
        tuple[LegalExpert, list[Document]]: A tuple containing the legal expert object and a list of
            documents extracted for that expert.
    """

    progress_bar = tqdm(
        experts,
        desc="Extracting docs",
        unit="expert",
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
        ncols=100,
        position=0,
        leave=True,
    )

    expert_factory = LegalExpertFactory()
    for expert_extract in progress_bar:
        expert = expert_factory.get_legal_expert(expert_extract.id)
        progress_bar.set_postfix_str(f"Expert: {expert.name}")

        expert_docs = extract(expert, expert_extract.urls)

        yield (expert, expert_docs)


def extract(expert: LegalExpert, extract_urls: list[str]) -> list[Document]:
    """Extract documents for a single legal expert from all sources.

    Args:
        expert: LegalExpert object containing expert information.
        extract_urls: List of URLs to extract content from.

    Returns:
        list[Document]: List of documents extracted for the expert.
    """

    docs = []

    # 1. Parse local legal documents (Constitution, Court Cases, etc.)
    logger.info(f"Loading local documents for {expert.name}...")
    try:
        loader = LegalDocumentLoader()
        local_docs = loader.load_expert_documents(expert.id, expert.name)
        docs.extend(local_docs)
    except Exception as e:
        logger.error(f"Error loading local documents: {e}")

    # 2. Add Wikipedia/Web sources as supplementary
    docs.extend(extract_wikipedia_legal(expert))
    docs.extend(extract_web_sources(expert, extract_urls))

    return docs


def extract_wikipedia_legal(expert: LegalExpert) -> list[Document]:
    """Extract documents for a single legal expert context from Wikipedia.

    Args:
        expert: LegalExpert object.

    Returns:
        list[Document]: List of documents extracted from Wikipedia.
    """
    try:
        loader = WikipediaLoader(
            query=expert.name + " Ghana Law", # Append context to search
            lang="en",
            load_max_docs=1,
            doc_content_chars_max=1000000,
        )
        docs = loader.load()

        for doc in docs:
            doc.metadata["expert_id"] = expert.id
            doc.metadata["expert_name"] = expert.name
        
        return docs
    except Exception:
        # Fallback if specific page not found
        return []


def extract_web_sources(
    expert: LegalExpert, urls: list[str]
) -> list[Document]:
    """Extract documents from provided URLs.

    Args:
        expert: LegalExpert object.
        urls: List of URLs to extract content from.

    Returns:
        list[Document]: List of documents extracted from URLs.
    """

    if len(urls) == 0:
        return []

    loader = WebBaseLoader(show_progress=False)
    soups = loader.scrape_all(urls)

    documents = []
    for url, soup in zip(urls, soups):
        # Basic text extraction
        text = soup.get_text(separator="\n\n", strip=True)
        
        metadata = {
            "source": url,
            "expert_id": expert.id,
            "expert_name": expert.name,
        }

        if title := soup.find("title"):
            metadata["title"] = title.get_text().strip(" \n")

        documents.append(Document(page_content=text, metadata=metadata))

    return documents


if __name__ == "__main__":
    expert = LegalExpertFactory().get_legal_expert("constitutional")
    print(f"Extracting for {expert.name}")
    docs = extract_wikipedia_legal(expert)
    print(docs)
