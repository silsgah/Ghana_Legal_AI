from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

    # --- GROQ Configuration ---
    GROQ_API_KEY: str
    GROQ_LLM_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_LLM_MODEL_CONTEXT_SUMMARY: str = "llama-3.1-8b-instant"
    
    # --- OpenAI Configuration (Required for evaluation) ---
    OPENAI_API_KEY: str

    # --- MongoDB Configuration ---
    MONGO_URI: str = Field(
        default="mongodb://ghana_legal:ghana_legal@local_dev_atlas:27017/?directConnection=true",
        description="Connection URI for the local MongoDB Atlas instance.",
    )
    MONGO_DB_NAME: str = "ghana_legal"
    MONGO_STATE_CHECKPOINT_COLLECTION: str = "legal_expert_state_checkpoints"
    MONGO_STATE_WRITES_COLLECTION: str = "legal_expert_state_writes"
    MONGO_LONG_TERM_MEMORY_COLLECTION: str = "legal_expert_long_term_memory"

    # --- Comet ML & Opik Configuration ---
    COMET_API_KEY: str | None = Field(
        default=None, description="API key for Comet ML and Opik services."
    )
    COMET_PROJECT: str = Field(
        default="ghana_legal_course",
        description="Project name for Comet ML and Opik tracking.",
    )

    # --- Agents Configuration ---
    TOTAL_MESSAGES_SUMMARY_TRIGGER: int = 30
    TOTAL_MESSAGES_AFTER_SUMMARY: int = 5

    # --- RAG Configuration ---
    RAG_TEXT_EMBEDDING_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAG_TEXT_EMBEDDING_MODEL_DIM: int = 384
    RAG_TOP_K: int = 3
    RAG_DEVICE: str = "cpu"
    RAG_CHUNK_SIZE: int = 256

    # --- LFM2/Ollama Configuration ---
    USE_LOCAL_LLM: bool = Field(
        default=False, description="Use local LFM2 model via Ollama instead of Groq"
    )
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "ghana-legal"  # Our fine-tuned LFM2 model

    # --- Real-Time Evaluation Configuration ---
    ENABLE_REALTIME_EVAL: bool = True
    EVAL_SAMPLE_RATE: float = 1.0  # 1.0 = all queries, 0.1 = 10%

    # --- Paths Configuration ---
    EVALUATION_DATASET_FILE_PATH: Path = Path("data/evaluation_dataset.json")
    EXTRACTION_METADATA_FILE_PATH: Path = Path("data/legal_experts.json")


settings = Settings()
