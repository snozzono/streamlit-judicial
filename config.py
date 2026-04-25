from dataclasses import dataclass


@dataclass
class Config:
    # API
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    api_base_url: str = "https://models.inference.ai.azure.com"

    # Indexación
    chunk_size: int = 512
    chunk_overlap: int = 80
    batch_size: int = 50
    docs_dir: str = "docs"
    vectorstore_dir: str = "vectorstore"

    # App
    k_default: int = 8
    temperature_default: float = 0.1
    max_query_length: int = 500


CONFIG = Config()
VECTORSTORE_FILES = ["index.faiss", "index.pkl"]
