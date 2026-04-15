# ⚖️ Asistente Tributario — Ruiz Salazar Tributaria

Asistente de consultas tributarias basado en RAG (*Retrieval-Augmented Generation*) sobre normativa chilena. Responde preguntas citando el artículo o decreto exacto, sin inventar normativa.

## Arquitectura

```
docs/             ← PDFs de la normativa (DL 824, DL 825, DL 830)
    │
    ▼
indexar.py        ← Carga, chunking y generación de embeddings
    │
    ▼
vectorstore/      ← Índice FAISS persistido (index.faiss + index.pkl)
    │
    ▼
app.py            ← Interfaz Streamlit + cadena RetrievalQA
```

**Stack:**

- **LLM:** `gpt-4o-mini` vía GitHub Models
- **Embeddings:** `text-embedding-3-small` vía GitHub Models
- **Vector store:** FAISS (local)
- **Framework:** LangChain + Streamlit

## Requisitos

- Python 3.10 – 3.13 (el proyecto **no es compatible con Python 3.14** por restricciones de Pydantic V1 en LangChain)
- Token de GitHub Models con acceso a la API de Azure AI Inference

## Instalación

```bash
git clone https://github.com/<tu-usuario>/ing-sol-parcial-1.git
cd ing-sol-parcial-1

pip install -r requirements.txt
```

Copia el archivo de ejemplo y agrega tu token:

```bash
cp .env.example .env
```

`.env`:

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

## Corpus normativo

Coloca los PDFs en la carpeta `docs/`. El proyecto incluye:


| Archivo                  | Descripción                                      |
| ------------------------ | ------------------------------------------------- |
| `DL-824_31-DIC-1974.pdf` | Ley sobre Impuesto a la Renta                     |
| `DL-825_31-DIC-1974.pdf` | Ley sobre Impuesto a las Ventas y Servicios (IVA) |
| `DL-830_31-DIC-1974.pdf` | Código Tributario                                |

## Indexación

Ejecutar **una sola vez** (o cada vez que se agreguen/modifiquen documentos):

```bash
python indexar.py
```

El script realiza lo siguiente:

1. Carga todos los PDFs en `docs/`
2. Divide el texto en chunks de ~512 tokens con solapamiento de 80 tokens
3. Genera embeddings en batches de 50 chunks para no exceder el límite de 64k tokens de GitHub Models
4. Guarda el índice FAISS en `vectorstore/`

Output esperado:

```
=== Indexando corpus normativo ===

1. Cargando PDFs...
  Cargando: DL-824_31-DIC-1974.pdf
  Cargando: DL-825_31-DIC-1974.pdf
  Cargando: DL-830_31-DIC-1974.pdf
  Total páginas cargadas: 483

2. Generando chunks...
  Total chunks generados: 2399

3. Generando embeddings y construyendo vectorstore...
  Procesando 2399 chunks en batches de 50...
  ...
  Vectorstore guardado en 'vectorstore/'

=== Indexación completada ===
```

## Ejecución

```bash
streamlit run app.py
```

La aplicación quedará disponible en `http://localhost:8501`.

## Uso

1. Escribe tu consulta tributaria en el campo de texto (ej: *¿Qué actividades están exentas de IVA según el artículo 12 del DL 825?*)
2. Ajusta el slider **"Fragmentos a recuperar (k)"** en el sidebar según la complejidad de la consulta (recomendado: 4–6)
3. Haz clic en **Consultar**
4. La respuesta incluye el análisis con citación de artículos y los fragmentos fuente expandibles

> ⚠️ Este asistente es orientativo. Las respuestas deben ser validadas por un contador o abogado tributario.

## Estructura del proyecto

```
ing-sol-parcial-1/
├── docs/                  # PDFs de normativa (no versionados)
├── vectorstore/           # Índice FAISS generado (no versionado)
│   ├── index.faiss
│   └── index.pkl
├── app.py                 # Aplicación Streamlit
├── indexar.py             # Script de indexación
├── requirements.txt       # Dependencias Python
├── .env                   # Variables de entorno (no versionado)
├── .env.example           # Plantilla de variables de entorno
└── .gitignore
```

## Dependencias

```
streamlit
langchain
langchain-openai
langchain-community
langchain-text-splitters
langchain-classic
faiss-cpu
pypdf
python-dotenv
openai
tiktoken
```

## Notas técnicas

**Chunking con tokenizer real:** El splitter usa `tiktoken` con la codificación `cl100k_base` para medir tokens reales en lugar de caracteres, evitando que chunks sobrepasen el límite del modelo de embeddings.

**Batching de embeddings:** GitHub Models limita las requests a 64k tokens acumulados. El script procesa los chunks en batches de 50 y fusiona los índices parciales con `FAISS.merge_from()`.

**Cache de la cadena:** `cargar_chain()` está decorada con `@st.cache_resource` y recibe `k` como parámetro, de modo que Streamlit reconstruye la cadena solo cuando cambia el valor del slider.

## Licencia

Proyecto académico — Ingeniería de Soluciones con IA, DuocUC.
