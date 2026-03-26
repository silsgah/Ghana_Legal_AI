"""Legal document parser for extracting structured information from legal texts."""

import re
from typing import List, Dict, Any
from dataclasses import dataclass
from langchain_core.documents import Document
from loguru import logger


@dataclass
class LegalDocument:
    """Structured representation of a legal document."""
    content: str
    title: str = ""
    article: str = ""
    section: str = ""
    subsection: str = ""
    court: str = ""
    case_number: str = ""
    date: str = ""
    citations: List[str] = None
    jurisdiction: str = "Ghana"
    document_type: str = "statute"  # constitution, case_law, statute, etc.


class LegalTextParser:
    """Parser for extracting legal structure from text documents."""
    
    def __init__(self):
        # Patterns for common legal document structures
        self.patterns = {
            # Matches article headings (e.g., "Article 12", "ARTICLE 12", "Article 12 - Equality")
            "article": re.compile(r"(?i)(?:article|art\.?)\s+(\d+)(?:\s*[-–—]\s*([^\n\r]+))?"),
            
            # Matches section headings (e.g., "Section 5", "SEC. 5", "Section 5 - Definitions")
            "section": re.compile(r"(?i)(?:section|sec\.?)\s+(\d+)(?:\((\d+)\))?"),
            
            # Matches subsection (e.g., "(1)", "(a)", "(i)")
            "subsection": re.compile(r"\((\w+)\)"),
            
            # Matches court names
            "court": re.compile(r"(?i)(Supreme\s+Court|Court\s+of\s+Appeal|High\s+Court|District\s+Court|Magistrate\s+Court)"),
            
            # Matches case numbers (e.g., "H.C. 1/2020", "CA/123/2020")
            "case_number": re.compile(r"[A-Z]+[./]\d+[/]\d{4}"),
            
            # Matches dates in various formats
            "date": re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b"),
            
            # Matches citations (e.g., "Constitution Article 12", "Section 5 of Act 123")
            "citation": re.compile(r"(?i)(?:article|section|act|chapter)\s+\d+(?:\s+[a-z]+\s+[a-z]+)?")
        }
    
    def parse_document(self, text: str, source: str = "") -> LegalDocument:
        """Parse a legal document and extract structured information.
        
        Args:
            text: The legal document text to parse
            source: Source identifier for the document
            
        Returns:
            LegalDocument: Structured representation of the legal document
        """
        # Extract the most relevant information
        doc = LegalDocument(content=text)
        
        # Extract article if present
        article_matches = self.patterns["article"].findall(text[:500])  # Check first 500 chars for article
        if article_matches:
            article_num, article_title = article_matches[0]
            doc.article = f"Article {article_num}"
            if article_title:
                doc.title = article_title.strip()
        
        # Extract section if present
        section_matches = self.patterns["section"].findall(text[:500])
        if section_matches:
            section_num = section_matches[0][0]
            subsection = section_matches[0][1] if len(section_matches[0]) > 1 and section_matches[0][1] else ""
            doc.section = f"Section {section_num}"
            if subsection:
                doc.subsection = f"({subsection})"
        
        # Extract court if present
        court_matches = self.patterns["court"].findall(text[:1000])
        if court_matches:
            doc.court = court_matches[0]
            doc.document_type = "case_law"
        
        # Extract case number if present
        case_matches = self.patterns["case_number"].findall(text)
        if case_matches:
            doc.case_number = case_matches[0]
        
        # Extract date if present
        date_matches = self.patterns["date"].findall(text)
        if date_matches:
            doc.date = date_matches[0]
        
        # Extract citations
        citation_matches = self.patterns["citation"].findall(text)
        doc.citations = list(set(citation_matches)) if citation_matches else []
        
        # If no specific article/section found, try to extract title from the first line
        if not doc.title:
            lines = text.strip().split('\n')
            if lines:
                first_line = lines[0].strip()
                if len(first_line) < 100:  # Only use short lines as potential titles
                    doc.title = first_line
        
        return doc
    
    def parse_documents(self, texts: List[str], sources: List[str] = None) -> List[LegalDocument]:
        """Parse multiple legal documents.
        
        Args:
            texts: List of legal document texts to parse
            sources: Optional list of source identifiers
            
        Returns:
            List of structured legal documents
        """
        if sources is None:
            sources = [f"doc_{i}" for i in range(len(texts))]
        
        parsed_docs = []
        for i, text in enumerate(texts):
            source = sources[i] if i < len(sources) else f"doc_{i}"
            parsed_doc = self.parse_document(text, source)
            parsed_docs.append(parsed_doc)
        
        return parsed_docs
    
    def create_langchain_documents(self, legal_docs: List[LegalDocument]) -> List[Document]:
        """Convert structured legal documents to LangChain documents.
        
        Args:
            legal_docs: List of structured legal documents
            
        Returns:
            List of LangChain Document objects
        """
        langchain_docs = []
        for i, legal_doc in enumerate(legal_docs):
            metadata = {
                "title": legal_doc.title,
                "article": legal_doc.article,
                "section": legal_doc.section,
                "subsection": legal_doc.subsection,
                "court": legal_doc.court,
                "case_number": legal_doc.case_number,
                "date": legal_doc.date,
                "citations": legal_doc.citations,
                "jurisdiction": legal_doc.jurisdiction,
                "document_type": legal_doc.document_type,
                "id": f"legal_doc_{i}"
            }
            
            # Remove None values from metadata
            metadata = {k: v for k, v in metadata.items() if v}
            
            langchain_doc = Document(
                page_content=legal_doc.content,
                metadata=metadata
            )
            langchain_docs.append(langchain_doc)
        
        return langchain_docs


def get_legal_parser() -> LegalTextParser:
    """Factory function to get a legal text parser.
    
    Returns:
        LegalTextParser: A configured legal document parser
    """
    logger.info("Initializing legal text parser")
    return LegalTextParser()