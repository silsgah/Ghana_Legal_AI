"""Abstract retriever protocol for the Ghana Legal AI RAG system.

Defines the interface that all retriever implementations (ChromaDB, Qdrant, etc.) must follow.
This ensures production-grade extensibility — new vector DB backends can be added
without modifying any consuming code.
"""

from typing import List, Optional, Protocol, runtime_checkable

from langchain_core.documents import Document


@runtime_checkable
class Retriever(Protocol):
    """Protocol defining the interface for all legal document retrievers.
    
    Any new vector database backend must implement these methods to be
    compatible with the rest of the system (LongTermMemory, RAG tools, etc.).
    """

    def retrieve(self, query: str) -> List[Document]:
        """Retrieve relevant documents for the given query.
        
        Args:
            query: Search query string.
            
        Returns:
            List of relevant LangChain Document objects.
        """
        ...

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Add texts to the vector store.
        
        Args:
            texts: List of text documents to add.
            metadatas: Optional metadata for each text.
            ids: Optional IDs for each text.
        """
        ...
