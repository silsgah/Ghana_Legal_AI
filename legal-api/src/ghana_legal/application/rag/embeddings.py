from langchain_voyageai import VoyageAIEmbeddings
from ghana_legal.config import settings

EmbeddingsModel = VoyageAIEmbeddings


def get_embedding_model(
    model_id: str,
    device: str = "cpu",
) -> EmbeddingsModel:
    """Gets an instance of a Voyage AI embedding model.

    Args:
        model_id (str): The ID/name of the Voyage AI embedding model to use (e.g., voyage-law-2)
        device (str): Deprecated/unused for Voyage AI, kept for interface compatibility.

    Returns:
        EmbeddingsModel: A configured Voyage AI embeddings model instance
    """
    return get_voyageai_embedding_model(model_id)


def get_voyageai_embedding_model(
    model_id: str
) -> VoyageAIEmbeddings:
    """Gets a Voyage AI embedding model instance.

    Args:
        model_id (str): The ID/name of the Voyage AI embedding model to use

    Returns:
        VoyageAIEmbeddings: A configured VoyageAIEmbeddings model instance
    """
    return VoyageAIEmbeddings(
        voyage_api_key=settings.VOYAGE_API_KEY,
        model=model_id,
    )
