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

def cargar_pdfs(directorio: str):
    docs = []
    pdfs = list(Path(directorio).glob("*.pdf"))
    
    if not pdfs:
        print(f"No se encontraron PDFs en '{directorio}/'")
        return []
    
    for pdf_path in pdfs:
        print(f"  Cargando: {pdf_path.name}")
        loader = PyPDFLoader(str(pdf_path))
        docs.extend(loader.load())
    
    print(f"  Total páginas cargadas: {len(docs)}")
    return docs

def contar_tokens(text: str) -> int:
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))

def crear_chunks(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,        # ahora en tokens reales, no caracteres
        chunk_overlap=80,
        length_function=contar_tokens,
        separators=["\n\n", "\n", ".", " "]
    )

def crear_vectorstore_en_batches(chunks, embeddings, batch_size=50):
    print(f"  Procesando {len(chunks)} chunks en batches de {batch_size}...")
    
    vectorstore = None
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        print(f"  Batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size} ({len(batch)} chunks)")
        
        if vectorstore is None:
            vectorstore = FAISS.from_documents(batch, embeddings)
        else:
            batch_vs = FAISS.from_documents(batch, embeddings)
            vectorstore.merge_from(batch_vs)
    
    return vectorstore

def indexar():
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