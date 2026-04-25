"""
indexar.py — Procesa los PDFs y genera el vectorstore FAISS.
Uso: python indexar.py

Ejecutar una sola vez, o cada vez que se agreguen documentos a docs/.
"""

import logging
import os
import sys

import tiktoken
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CONFIG
from utils import get_embeddings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()


def cargar_pdfs(directorio: str) -> list:
    archivos = sorted(f for f in os.listdir(directorio) if f.endswith(".pdf"))
    if not archivos:
        logger.error("No se encontraron PDFs en '%s/'", directorio)
        sys.exit(1)

    documentos = []
    for archivo in archivos:
        ruta = os.path.join(directorio, archivo)
        logger.info("  Cargando: %s", archivo)
        loader = PyPDFLoader(ruta)
        docs = loader.load()
        documentos.extend(docs)

    return documentos


def dividir_chunks(documentos: list) -> list:
    enc = tiktoken.get_encoding("cl100k_base")

    def longitud_tokens(texto: str) -> int:
        return len(enc.encode(texto))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CONFIG.chunk_size,
        chunk_overlap=CONFIG.chunk_overlap,
        length_function=longitud_tokens,
    )
    return splitter.split_documents(documentos)


def generar_vectorstore(chunks: list, api_key: str) -> None:
    embeddings = get_embeddings(api_key)
    os.makedirs(CONFIG.vectorstore_dir, exist_ok=True)

    total = len(chunks)
    total_batches = (total + CONFIG.batch_size - 1) // CONFIG.batch_size
    vectorstore = None

    for i in range(0, total, CONFIG.batch_size):
        batch = chunks[i : i + CONFIG.batch_size]
        num_batch = i // CONFIG.batch_size + 1
        logger.info("  Batch %d/%d (%d chunks)...", num_batch, total_batches, len(batch))

        partial = FAISS.from_documents(batch, embeddings)
        if vectorstore is None:
            vectorstore = partial
        else:
            vectorstore.merge_from(partial)

    vectorstore.save_local(CONFIG.vectorstore_dir)
    logger.info("  Vectorstore guardado en '%s/'", CONFIG.vectorstore_dir)


def main() -> None:
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        logger.error("GITHUB_TOKEN no encontrado. Revisa tu .env")
        sys.exit(1)

    if not os.path.exists(CONFIG.docs_dir):
        logger.error("Directorio '%s/' no encontrado.", CONFIG.docs_dir)
        sys.exit(1)

    print("\n=== Indexando corpus normativo ===\n")

    print("1. Cargando PDFs...")
    documentos = cargar_pdfs(CONFIG.docs_dir)
    print(f"   Total páginas cargadas: {len(documentos)}\n")

    print("2. Generando chunks...")
    chunks = dividir_chunks(documentos)
    print(f"   Total chunks generados: {len(chunks)}\n")

    print("3. Generando embeddings y construyendo vectorstore...")
    print(f"   Procesando {len(chunks)} chunks en batches de {CONFIG.batch_size}...")
    generar_vectorstore(chunks, api_key)

    print("\n=== Indexación completada ===\n")


if __name__ == "__main__":
    main()
