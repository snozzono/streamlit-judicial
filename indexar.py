import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import tiktoken

load_dotenv()

DOCS_DIR = "docs"
VECTORSTORE_DIR = "vectorstore"

# Instanciar el tokenizador una sola vez a nivel de módulo.
# tiktoken.get_encoding() carga el vocabulario desde disco/caché; instanciarlo
# dentro de contar_tokens() lo repetiría cientos de veces durante el splitting,
# una por cada fragmento candidato que el splitter evalúa.
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def cargar_pdfs(directorio: str) -> list:
    """
    Carga todos los archivos PDF del directorio indicado usando PyPDFLoader.
    Cada página del PDF se convierte en un Document de LangChain con metadata
    que incluye 'source' y 'page', usados luego para citar fuentes en la UI.

    Args:
        directorio: Ruta al directorio que contiene los PDFs.

    Returns:
        Lista de Documents. Lista vacía si no hay PDFs.
    """
    pdfs = list(Path(directorio).glob("*.pdf"))

    if not pdfs:
        print(f"No se encontraron PDFs en '{directorio}/'")
        return []

    docs = []
    for pdf_path in pdfs:
        print(f"  Cargando: {pdf_path.name}")
        loader = PyPDFLoader(str(pdf_path))
        docs.extend(loader.load())

    print(f"  Total páginas cargadas: {len(docs)}")
    return docs


def contar_tokens(text: str) -> int:
    """
    Cuenta tokens usando el tokenizador cl100k_base (mismo que usa
    text-embedding-3-small y gpt-4o-mini). Se pasa como length_function
    al splitter para que los chunks respeten límites reales del modelo
    en lugar de contar caracteres, lo que puede subestimar o sobreestimar
    el tamaño real del contexto enviado a la API.

    Args:
        text: Texto a tokenizar.

    Returns:
        Cantidad de tokens.
    """
    return len(_TOKENIZER.encode(text))


def crear_chunks(docs: list) -> list:
    """
    Divide los Documents en fragmentos (chunks) de hasta 512 tokens con
    solapamiento de 80 tokens.

    El solapamiento garantiza que conceptos que cruzan el límite de un chunk
    (por ejemplo, un artículo que continúa en la página siguiente) no queden
    partidos sin contexto en ambos lados.

    Los separadores se prueban en orden de preferencia: párrafo > línea >
    punto > espacio, para preservar la estructura semántica del texto legal.

    Args:
        docs: Lista de Documents a dividir.

    Returns:
        Lista de chunks listos para vectorizar.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=80,
        length_function=contar_tokens,
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(docs)
    print(f"  Total chunks generados: {len(chunks)}")
    return chunks


def crear_vectorstore_en_batches(chunks: list, embeddings, batch_size: int = 50) -> FAISS:
    """
    Vectoriza los chunks en lotes y construye un índice FAISS fusionando
    los índices parciales con FAISS.merge_from().

    Por qué batches: GitHub Models limita las requests de embeddings a ~64k
    tokens acumulados. Enviar los 2399 chunks de una vez excedería ese límite
    y devolvería un error 429. Con batch_size=50 (~25k tokens por lote)
    se mantiene un margen seguro.

    Args:
        chunks:     Lista completa de chunks a vectorizar.
        embeddings: Instancia de OpenAIEmbeddings configurada.
        batch_size: Chunks por lote (default 50).

    Returns:
        Índice FAISS con todos los embeddings.
    """
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    print(f"  Procesando {len(chunks)} chunks en {total_batches} batches de {batch_size}...")

    vectorstore = None
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        num_batch = i // batch_size + 1
        print(f"  Batch {num_batch}/{total_batches} ({len(batch)} chunks)")

        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            batch_vs = FAISS.from_documents(batch, embeddings)
            vectorstore.merge_from(batch_vs)

    return vectorstore


def indexar():
    """
    Orquesta el pipeline completo de indexación:
        1. Carga PDFs desde docs/
        2. Divide en chunks con tokenización real
        3. Genera embeddings en batches y construye el índice FAISS
        4. Persiste el índice en vectorstore/

    Este script se ejecuta una sola vez (o cada vez que cambie el corpus).
    El índice generado es consumido por app.py en tiempo de consulta.
    """
    print("=== Indexando corpus normativo ===\n")

    print("1. Cargando PDFs...")
    docs = cargar_pdfs(DOCS_DIR)
    if not docs:
        return

    print("\n2. Generando chunks...")
    chunks = crear_chunks(docs)

    print("\n3. Generando embeddings y construyendo vectorstore...")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        base_url="https://models.inference.ai.azure.com",
        api_key=os.getenv("GITHUB_TOKEN")
    )

    vectorstore = crear_vectorstore_en_batches(chunks, embeddings, batch_size=50)
    vectorstore.save_local(VECTORSTORE_DIR)
    print(f"  Vectorstore guardado en '{VECTORSTORE_DIR}/'")
    print("\n=== Indexación completada ===")


if __name__ == "__main__":
    indexar()