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
    MONGO_MODE: str = Field(
        default="local",
        description="MongoDB connection mode: 'local' for local MongoDB, 'atlas' for MongoDB Atlas"
    )
    MONGO_LOCAL_URI: str = Field(
        default="mongodb://localhost:27017/ghana_legal",
        description="Connection URI for local MongoDB instance.",
    )
    MONGO_ATLAS_URI: str = Field(
        default="mongodb+srv://ghana_legal:ghana_legal@local_dev_atlas:27017/?directConnection=true",
        description="Connection URI for the MongoDB Atlas instance.",
    )
    MONGO_DB_NAME: str = "ghana_legal"
    MONGO_STATE_CHECKPOINT_COLLECTION: str = "legal_expert_state_checkpoints"
    MONGO_STATE_WRITES_COLLECTION: str = "legal_expert_state_writes"
    MONGO_LONG_TERM_MEMORY_COLLECTION: str = "legal_expert_long_term_memory"

    @property
    def MONGO_URI(self) -> str:
        """Return the appropriate MongoDB URI based on the connection mode"""
        if self.MONGO_MODE == "local":
            return getattr(self, 'MONGO_LOCAL_URI_OVERRIDE', None) or self.MONGO_LOCAL_URI
        else:  # atlas mode
            return getattr(self, 'MONGO_ATLAS_URI_OVERRIDE', None) or self.MONGO_ATLAS_URI

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

    # --- Vector Database Configuration ---
    VECTOR_DB_MODE: str = Field(
        default="chroma",
        description="Vector database mode: 'chroma' for local dev, 'qdrant' for production",
    )
    QDRANT_URL: str = Field(default="", description="Qdrant Cloud cluster URL")
    QDRANT_API_KEY: str = Field(default="", description="Qdrant Cloud API key")

    # --- PostgreSQL Configuration ---
    DATABASE_URL: str = Field(default="", description="PostgreSQL connection string")
    FREE_TIER_DAILY_LIMIT: int = Field(default=5, description="Number of free queries per day")

    # --- Clerk Configuration ---
    CLERK_SECRET_KEY: str = Field(default="", description="Clerk secret key for Backend API calls (sk_live_... or sk_test_...)")

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
