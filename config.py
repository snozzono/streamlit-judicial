from dataclasses import dataclass, field


@dataclass
class Config:
    # --- API ---
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    api_base_url: str = "https://models.inference.ai.azure.com"

    # --- Indexación ---
    chunk_size: int = 512
    chunk_overlap: int = 80
    batch_size: int = 50
    docs_dir: str = "docs"
    vectorstore_dir: str = "vectorstore"

    # --- App (EP1, sin cambios) ---
    k_default: int = 8
    temperature_default: float = 0.1
    max_query_length: int = 500

    # --- Agente (EP2) ---
    max_reasoning_iterations: int = 2   # loops máximos en el nodo razonador
    confianza_minima: float = 0.7       # umbral para considerar contexto suficiente

    # --- Rutas EP2 ---
    casos_dir: str = "casos"
    memos_dir: str = "memos"
    casos_index: str = "casos/casos.index"
    casos_pkl: str = "casos/casos.pkl"

    # --- Anonimización ---
    entidades_sensibles: tuple = ("RUT", "NOMBRE", "EMPRESA", "DIRECCION", "EMAIL")


CONFIG = Config()

# EP1 — sin cambios
VECTORSTORE_FILES = ["index.faiss", "index.pkl"]