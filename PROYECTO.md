# Asistente Tributario — Ruiz Salazar Tributaria

**Proyecto:** Parcial 1 — Ingeniería de Soluciones con IA  
**Institución:** DuocUC  
**Fecha:** Abril 2026

---

## Índice

1. [¿Qué hace el proyecto?](#1-qué-hace-el-proyecto)
2. [¿Qué es RAG?](#2-qué-es-rag)
3. [Arquitectura del sistema](#3-arquitectura-del-sistema)
4. [Stack tecnológico](#4-stack-tecnológico)
5. [Cómo funciona paso a paso](#5-cómo-funciona-paso-a-paso)
6. [Estructura de archivos](#6-estructura-de-archivos)
7. [La interfaz de usuario](#7-la-interfaz-de-usuario)
8. [Cómo correr el proyecto](#8-cómo-correr-el-proyecto)
9. [Resultados de los tests](#9-resultados-de-los-tests)
10. [Mejoras propuestas](#10-mejoras-propuestas)

---

## 1. ¿Qué hace el proyecto?

El proyecto es un **asistente de consultas tributarias** que responde preguntas sobre la normativa tributaria chilena, citando los artículos exactos de la ley en los que basa sus respuestas.

Un usuario puede preguntar cosas como:

> *"¿Cuál es la tasa del IVA en Chile y en qué casos hay tasa diferenciada?"*  
> *"¿Qué actividades están exentas del impuesto a la renta?"*  
> *"¿Cuáles son las obligaciones de un contribuyente de primera categoría?"*

Y el sistema responde con:

- **Análisis:** explicación detallada basada en los textos legales
- **Artículos citados:** los artículos exactos del decreto ley en que se fundamenta
- **Limitaciones:** lo que no puede responder con certeza

El corpus de conocimiento son tres decretos ley chilenos:

| Decreto | Contenido |
|---------|-----------|
| DL-824 (1974) | Ley sobre Impuesto a la Renta (192 páginas) |
| DL-825 (1974) | Ley sobre IVA — Ventas y Servicios (53 páginas) |
| DL-830 (1974) | Código Tributario (177 páginas) |

---

## 2. ¿Qué es RAG?

**RAG** significa *Retrieval-Augmented Generation* (Generación Aumentada por Recuperación). Es una técnica que combina dos capacidades:

1. **Retrieval (Recuperación):** buscar los fragmentos más relevantes dentro de una base de documentos
2. **Generation (Generación):** usar un LLM para redactar la respuesta basándose en esos fragmentos

### El problema que resuelve

Los modelos de lenguaje (como GPT-4) tienen dos limitaciones para este caso:

- **No conocen documentos privados o específicos:** el DL-824 puede estar en sus datos de entrenamiento, pero no en versión exacta ni actualizada
- **Alucinan:** pueden inventar artículos que no existen

Con RAG, en lugar de dejar que el modelo "recuerde" la ley de memoria, le damos los fragmentos exactos del texto legal como contexto para cada pregunta. El modelo solo puede citar lo que tiene delante.

### Comparación

| Sin RAG | Con RAG |
|---------|---------|
| El modelo responde desde su entrenamiento | El modelo responde desde los documentos reales |
| Puede inventar artículos | Solo cita lo que encuentra en el texto |
| No actualizable fácilmente | Se actualiza cambiando los PDFs |
| No da fuentes verificables | Indica página y archivo fuente |

---

## 3. Arquitectura del sistema

```
┌─────────────────────────────────────────────────────────┐
│                     FASE DE INDEXACIÓN                  │
│                    (se hace una vez)                    │
│                                                         │
│   docs/                                                 │
│   ├── DL-824.pdf  ──┐                                   │
│   ├── DL-825.pdf  ──┤──► Carga PDF ──► Chunking         │
│   └── DL-830.pdf  ──┘                     │             │
│                                           ▼             │
│                               Modelo de Embeddings      │
│                               (text-embedding-3-small)  │
│                                           │             │
│                                           ▼             │
│                                    vectorstore/         │
│                                    index.faiss          │
│                                    index.pkl            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  FASE DE CONSULTA                       │
│                  (cada vez que el usuario pregunta)     │
│                                                         │
│  Usuario: "¿Cuál es la tasa del IVA?"                   │
│                │                                        │
│                ▼                                        │
│    Embedding de la pregunta                             │
│                │                                        │
│                ▼                                        │
│    Búsqueda de similitud en FAISS                       │
│    (recupera los k fragmentos más relevantes)           │
│                │                                        │
│                ▼                                        │
│    Fragmentos recuperados:                              │
│    - "Art. 14 DL-825: La tasa del IVA es 19%..."        │
│    - "Art. 15 DL-825: Se exceptúan los casos..."        │
│    - ...                                                │
│                │                                        │
│                ▼                                        │
│    Prompt al LLM (gpt-4o-mini):                         │
│    [system prompt] + [fragmentos] + [pregunta]          │
│                │                                        │
│                ▼                                        │
│    Respuesta estructurada:                              │
│    ## Análisis / ## Artículos citados / ## Limitaciones │
│                │                                        │
│                ▼                                        │
│    Interfaz Streamlit                                   │
└─────────────────────────────────────────────────────────┘
```

### Componentes clave

**FAISS (Facebook AI Similarity Search)**  
Base de datos vectorial que almacena los embeddings de todos los fragmentos. Permite hacer búsquedas de similitud semántica en milisegundos, incluso con miles de fragmentos.

**Embeddings**  
Representación numérica de un texto (un vector de 1536 números para `text-embedding-3-small`). Textos con significado similar tienen vectores cercanos en el espacio vectorial. Esto permite encontrar fragmentos relevantes aunque no usen las mismas palabras exactas que la pregunta.

**Chain type "stuff"**  
LangChain tiene varias estrategias para pasar documentos al LLM. "Stuff" es la más simple: mete todos los fragmentos recuperados directamente en el prompt. Funciona bien cuando `k` no es muy alto.

---

## 4. Stack tecnológico

| Categoría | Tecnología | Para qué se usa |
|-----------|-----------|----------------|
| LLM | `gpt-4o-mini` vía GitHub Models | Generar las respuestas en lenguaje natural |
| Embeddings | `text-embedding-3-small` vía GitHub Models | Convertir texto a vectores numéricos |
| Vector Store | FAISS (local) | Almacenar y buscar embeddings |
| RAG Framework | LangChain | Conectar todas las piezas del pipeline |
| UI | Streamlit | Interfaz web interactiva |
| PDF Loader | PyPDF (LangChain) | Extraer texto de los PDFs |
| Tokenizador | tiktoken (cl100k_base) | Medir tokens reales al dividir texto |
| Secretos | python-dotenv | Cargar el token desde `.env` |

### ¿Por qué GitHub Models?

GitHub Models ofrece acceso gratuito (con límite) a modelos de OpenAI usando un token de GitHub personal. La API es compatible con el SDK de OpenAI, por eso el código usa `OpenAIEmbeddings` y `ChatOpenAI` apuntando a la URL de Azure AI Inference de GitHub.

```python
# El "truco": misma API de OpenAI, distinta URL base
llm = ChatOpenAI(
    model="gpt-4o-mini",
    base_url="https://models.inference.ai.azure.com",  # ← GitHub Models
    api_key=os.getenv("GITHUB_TOKEN"),                  # ← token de GitHub
)
```

---

## 5. Cómo funciona paso a paso

### Paso 1 — Chunking (dividir el texto)

Los PDFs tienen cientos de páginas. No se pueden meter enteros en el contexto del LLM (límite de tokens). Se dividen en fragmentos:

```
Documento completo (192 páginas)
    │
    ▼
Chunk 1: "Artículo 1. Para los efectos de la presente ley..."    (~512 tokens)
Chunk 2: "...las rentas de fuente chilena serán gravadas..."      (~512 tokens)
Chunk 3: "Artículo 2. Se entiende por renta..."                  (~512 tokens)
    ...
Chunk 2399: último fragmento del DL-830
```

**Parámetros usados:**
- Tamaño de chunk: **512 tokens** (medido con tiktoken, no caracteres)
- Solapamiento: **80 tokens** (para no cortar frases importantes en el borde)

El solapamiento asegura que si un artículo queda partido entre dos chunks, ambos chunks tienen suficiente contexto para ser interpretados.

### Paso 2 — Embeddings

Cada chunk se convierte en un vector numérico usando `text-embedding-3-small`. Como hay ~2399 chunks y GitHub Models tiene un límite de 64k tokens por request, se procesan en batches de 50:

```python
for i in range(0, len(chunks), 50):
    batch = chunks[i:i+50]
    partial_store = FAISS.from_documents(batch, embeddings)
    vectorstore.merge_from(partial_store)  # fusionar con el índice principal
```

### Paso 3 — Búsqueda semántica

Cuando el usuario hace una pregunta, se convierte también a embedding y se buscan los `k` chunks más similares en FAISS. La similitud se mide con **distancia coseno** entre vectores.

Esto es diferente a una búsqueda por palabras clave: aunque el usuario pregunte por "exenciones del impuesto", puede encontrar fragmentos que hablen de "liberaciones tributarias" porque semánticamente son similares.

### Paso 4 — Prompt al LLM

Los fragmentos recuperados se insertan en el prompt junto con la pregunta:

```
Eres un asistente de consultas tributarias...

Contexto normativo recuperado:
[Fragmento 1: "Art. 14 DL-825: La tasa del IVA es 19%..."]
[Fragmento 2: "Art. 15 DL-825: Se exceptúan..."]
... (k fragmentos)

Pregunta: ¿Cuál es la tasa del IVA?

Estructura tu respuesta con estos tres encabezados:
## Análisis
## Artículos citados
## Limitaciones
```

### Paso 5 — Parseo de la respuesta

El LLM devuelve texto con los tres encabezados. La función `parsear_respuesta()` divide el texto en sus secciones para mostrarlas en la UI de forma organizada:

```python
def parsear_respuesta(texto: str) -> dict:
    secciones = {"analisis": "", "articulos": "", "limitaciones": ""}
    marcadores = {
        "## Análisis": "analisis",
        "## Artículos citados": "articulos",
        "## Limitaciones": "limitaciones",
    }
    seccion_actual = None
    buffer = []
    for linea in texto.splitlines():
        if linea.strip() in marcadores:
            if seccion_actual:
                secciones[seccion_actual] = "\n".join(buffer).strip()
            seccion_actual = marcadores[linea.strip()]
            buffer = []
        else:
            buffer.append(linea)
    # guardar la última sección
    if seccion_actual:
        secciones[seccion_actual] = "\n".join(buffer).strip()
    return secciones
```

---

## 6. Estructura de archivos

```
ing-sol-parcial-1/
│
├── docs/                        # PDFs del corpus (no versionados en git)
│   ├── DL-824_31-DIC-1974.pdf
│   ├── DL-825_31-DIC-1974.pdf
│   └── DL-830_31-DIC-1974.pdf
│
├── vectorstore/                 # Índice FAISS generado (no versionado en git)
│   ├── index.faiss              # El índice binario de FAISS
│   └── index.pkl                # Metadatos y configuración del índice
│
├── indexar.py                   # Aplicación Streamlit activa (versión completa)
├── app.py                       # Versión anterior de la app (más simple)
├── test_queries.py              # Suite de tests automatizados (9 casos)
│
├── requirements.txt             # Dependencias Python
├── .env                         # Token de GitHub (NO subir a git)
├── .env.example                 # Plantilla de .env
├── .gitignore
└── README.md
```

> **Nota sobre `indexar.py` y `app.py`:** El README describe `indexar.py` como el script de indexación (procesamiento de PDFs), pero actualmente contiene la aplicación Streamlit completa. El script de indexación original fue sobreescrito. Esta es una de las mejoras identificadas en la sección 10.

---

## 7. La interfaz de usuario

La app está hecha con **Streamlit**, que convierte código Python en una web app sin necesidad de HTML/CSS/JS.

```
┌─────────────────────────────────────────────────────────────┐
│  Sidebar                │  Col izquierda   │  Col derecha   │
│  ─────────────          │  ─────────────── │  ────────────  │
│  ⚙️ k slider: 1–8      │  💬 Consulta     │  🕓 Historial  │
│  🌡️ Temperatura: 0–1   │  [text area]     │  1. ¿Qué es... │
│  ─────────────          │  [Consultar btn] │  2. ¿Cuál...   │
│  📚 Corpus:             │                  │  ...           │
│  - DL 824               │  📋 Respuesta    │                │
│  - DL 825               │  Análisis...     │  [🗑️ Limpiar]  │
│  - DL 830               │  Artículos...    │  [📥 Exportar] │
│  ─────────────          │  Limitaciones... │                │
│  ⚠️ Disclaimer          │                  │                │
│                         │  📎 Fuentes (k)  │                │
│                         │  > Fragmento 1   │                │
│                         │  > Fragmento 2   │                │
└─────────────────────────────────────────────────────────────┘
```

### Parámetros configurables desde la UI

**k (fragmentos a recuperar):** cuántos chunks del vectorstore se recuperan para responder. Más chunks = más contexto = respuestas más completas, pero también más tokens enviados al LLM (más costo y latencia).

**Temperatura:** controla qué tan "creativo" es el LLM.
- `0.0` → respuestas deterministas, siempre igual ante la misma pregunta
- `1.0` → respuestas más variables y creativas
- Para derecho tributario se recomienda `0.1` (precisión sobre creatividad)

### Caché de Streamlit

La app usa `@st.cache_resource` para no recargar el vectorstore con cada interacción:

```python
@st.cache_resource          # solo carga una vez por sesión
def cargar_modelos():       # ← el vectorstore no cambia
    vectorstore = FAISS.load_local(...)
    return vectorstore, embeddings

@st.cache_resource
def cargar_chain(k: int, temperature: float):   # ← esta sí varía con los sliders
    vectorstore, _ = cargar_modelos()            # viene del caché
    llm = ChatOpenAI(temperature=temperature)
    ...
```

---

## 8. Cómo correr el proyecto

### Requisitos
- Python 3.10 a 3.13 (no compatible con 3.14)
- Token de GitHub con acceso a GitHub Models

### Instalación

```bash
git clone https://github.com/<usuario>/ing-sol-parcial-1.git
cd ing-sol-parcial-1
pip install -r requirements.txt
```

### Configuración

```bash
cp .env.example .env
# Editar .env y poner el token:
# GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

### Ejecutar la app

```bash
streamlit run indexar.py
```

La app queda disponible en `http://localhost:8501`

### Correr los tests

```bash
python test_queries.py
# Genera test_results.md con el detalle de cada test
```

---

## 9. Resultados de los tests

El archivo `test_queries.py` tiene 9 casos de prueba automatizados:

| Test | Consulta | Resultado |
|------|----------|-----------|
| T01 | Impuesto primera categoría (DL-824) | ✅ PASS |
| T02 | Tasa IVA y tasa diferenciada (DL-825) | ❌ FAIL |
| T03 | Exenciones IVA (DL-825) | ✅ PASS |
| T04 | Prescripción tributaria (DL-830) | ✅ PASS |
| T05 | Gastos necesarios para producir renta (DL-824) | ✅ PASS |
| T06 | Sanciones por no declarar (DL-830) | ✅ PASS |
| T07 | Impuesto adicional para extranjeros (DL-824) | ✅ PASS |
| T08 | Pregunta fuera del corpus tributario | ✅ PASS |
| T09 | Visa de trabajo (fuera de corpus) | ❌ FAIL |

**T02 falla** porque el modelo responde "normativa no disponible" sin generar las secciones `## Artículos citados` ni `## Limitaciones`. Probablemente k=4 no recupera suficientes fragmentos del DL-825 para responder esa pregunta específica.

**T09 falla** porque el modelo detecta correctamente que la pregunta está fuera del corpus tributario, pero no completa la sección `## Limitaciones` como lo exige el prompt.

---

## 10. Mejoras propuestas

A continuación se describen las mejoras identificadas, ordenadas por prioridad.

---

### 🔴 CRÍTICO

#### 10.1 Rotar el token de GitHub expuesto

**Problema:** El archivo `.env` contiene un token real de GitHub. Aunque está en `.gitignore`, quedó expuesto en el historial de git o en el sistema de archivos.

**Impacto:** Cualquier persona con acceso puede usar ese token para hacer llamadas a la API y agotar la cuota.

**Solución:**
1. Ir a GitHub → Settings → Developer Settings → Personal access tokens → Revocar el token actual
2. Generar uno nuevo con permisos mínimos (`read:models` únicamente)
3. Agregar validación temprana en el código:

```python
token = os.getenv("GITHUB_TOKEN")
if not token:
    raise EnvironmentError("GITHUB_TOKEN no encontrado. Revisa tu .env")
if not token.startswith("github_pat_") and not token.startswith("ghp_"):
    raise ValueError("GITHUB_TOKEN no tiene el formato esperado.")
```

---

#### 10.2 Separar `indexar.py` en un script independiente

**Problema:** `indexar.py` tiene la aplicación Streamlit completa. Debería ser un script standalone que solo procese los PDFs y genere el vectorstore. Actualmente es imposible regenerar el vectorstore ejecutando `python indexar.py` como dice el README.

**Por qué importa:** Si se agregan nuevos PDFs al corpus, no hay forma de regenerar el vectorstore sin ejecutar toda la app.

**Principio aplicado:** Responsabilidad única — cada módulo debe tener una sola razón para existir.

**Solución — separar en dos archivos:**

`indexar.py` (solo indexación, sin Streamlit):
```python
"""Procesa los PDFs y genera el vectorstore FAISS. Uso: python indexar.py"""
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

def cargar_pdfs(directorio: str):
    documentos = []
    for archivo in os.listdir(directorio):
        if archivo.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(directorio, archivo))
            documentos.extend(loader.load())
    return documentos

if __name__ == "__main__":
    docs = cargar_pdfs("docs")
    # ... chunking y generación de vectorstore
```

`app.py` (solo la UI Streamlit):
```python
import streamlit as st
# ... cargar vectorstore ya existente y responder preguntas
```

---

### 🟠 ALTO

#### 10.3 Corregir `requirements.txt`

**Problema:** Faltan dependencias en el archivo. Hacer `pip install -r requirements.txt` no instala todo lo necesario.

```diff
+ tiktoken==0.12.0    # usado en el script de indexación
+ pypdf==6.10.2       # necesario para PyPDFLoader
```

---

#### 10.4 Centralizar la configuración en `config.py`

**Problema:** Los parámetros importantes están hardcodeados en múltiples archivos, con valores distintos:

```python
# En indexar.py       # En app.py      # En test_queries.py
chunk_size = 512      k_docs = 4       k = 3
batch_size = 50
```

**Solución:**
```python
# config.py — un solo lugar para cambiar todo
from dataclasses import dataclass

@dataclass
class Config:
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    api_base_url: str = "https://models.inference.ai.azure.com"
    chunk_size: int = 512
    chunk_overlap: int = 80
    batch_size: int = 50
    k_default: int = 4
    temperature_default: float = 0.1

CONFIG = Config()
```

---

#### 10.5 Eliminar código duplicado en `utils.py`

**Problema:** Hay código idéntico en tres archivos:

| Código duplicado | Dónde aparece |
|---|---|
| `SYSTEM_PROMPT` | `app.py`, `indexar.py`, `test_queries.py` |
| `parsear_respuesta()` | `indexar.py`, `test_queries.py` |
| Configuración del cliente OpenAI | Los tres archivos |

Si el prompt cambia, hay que actualizarlo en tres lugares y es fácil olvidarse de uno.

**Solución:** crear `utils.py` con lo compartido e importarlo desde los otros archivos.

---

### 🟡 MEDIO

#### 10.6 Corregir los tests fallidos

**T02 (IVA):** aumentar `k` a 6–8 para esa consulta, o revisar si el DL-825 está bien indexado.

**T09 (fuera de corpus):** ajustar el prompt para que indique explícitamente qué escribir en `## Limitaciones` cuando la pregunta está fuera del corpus:

```
## Limitaciones
- Si la consulta está dentro del corpus: indica qué aspectos no puedes confirmar.
- Si la consulta está FUERA del corpus tributario: indica explícitamente que el 
  tema no está cubierto por DL-824, DL-825 ni DL-830.
```

---

#### 10.7 Optimizar el caché de Streamlit

**Problema actual:** cuando el usuario mueve el slider de temperatura, Streamlit reconstruye la `chain` completa incluyendo recargar el vectorstore desde disco.

**Solución:** separar el caché del vectorstore (que nunca cambia) del caché de la chain (que varía con los sliders):

```python
@st.cache_resource          # se carga UNA sola vez
def cargar_vectorstore():
    return FAISS.load_local(...)

def crear_chain(k, temperature):
    vs = cargar_vectorstore()   # viene del caché
    llm = ChatOpenAI(temperature=temperature)
    return RetrievalQA.from_chain_type(llm=llm, ...)
```

---

#### 10.8 Agregar type hints

**Problema:** sin type hints, es difícil saber qué recibe y devuelve cada función sin leerla entera.

```python
# Actual
def parsear_respuesta(texto):
    secciones = {}
    ...

# Mejorado
def parsear_respuesta(texto: str) -> dict[str, str]:
    secciones: dict[str, str] = {}
    ...
```

---

#### 10.9 Validar el input del usuario

**Problema:** el texto del usuario va directo al LLM sin validación. Permite **prompt injection**: escribir instrucciones para que el modelo ignore las reglas del sistema.

**Solución:**
```python
MAX_QUERY_LENGTH = 500

def validar_consulta(texto: str) -> str:
    texto = texto.strip()
    if not texto:
        raise ValueError("La consulta no puede estar vacía.")
    if len(texto) > MAX_QUERY_LENGTH:
        raise ValueError(f"Máximo {MAX_QUERY_LENGTH} caracteres.")
    return texto
```

---

#### 10.10 Agregar manejo de errores con reintentos en la API

**Problema:** si la API de GitHub Models falla (rate limit, timeout), la app lanza un error sin contexto.

**Solución:**
```python
import time
from openai import RateLimitError

def llamar_con_reintento(chain, consulta, max_intentos=3):
    for intento in range(max_intentos):
        try:
            return chain.invoke({"query": consulta})
        except RateLimitError:
            if intento < max_intentos - 1:
                time.sleep(2 ** intento)  # espera: 1s, 2s, 4s
            else:
                raise
```

---

### 🟢 BAJO

#### 10.11 Reemplazar `print()` con `logging`

```python
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# En lugar de print():
logger.info(f"Procesando batch {i+1}/{total}...")
logger.error("Error al cargar el vectorstore", exc_info=True)
```

---

#### 10.12 Implementar el botón "Exportar"

El botón existe en la UI pero está deshabilitado. Implementación básica:

```python
import json

if st.button("📥 Exportar historial"):
    contenido = json.dumps(st.session_state.historial, ensure_ascii=False, indent=2)
    st.download_button("Descargar JSON", contenido, "historial.json", "application/json")
```

---

#### 10.13 Agregar tests unitarios

Los tests actuales son de integración (end-to-end con la API). Agregar tests unitarios para `parsear_respuesta()`:

```python
def test_parsear_respuesta_completa():
    texto = "## Análisis\nHay IVA.\n## Artículos citados\nArt. 14.\n## Limitaciones\nNinguna."
    resultado = parsear_respuesta(texto)
    assert resultado["analisis"] == "Hay IVA."
    assert resultado["articulos"] == "Art. 14."
    assert resultado["limitaciones"] == "Ninguna."
```

---

#### 10.14 Agregar CI/CD con GitHub Actions

Automatizar los tests para que corran en cada push:

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python test_queries.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

### Resumen de prioridades

| # | Mejora | Esfuerzo | Impacto | Prioridad |
|---|--------|----------|---------|-----------|
| 10.1 | Rotar token expuesto | Bajo | Alto | 🔴 Crítico |
| 10.2 | Separar `indexar.py` del código de la app | Medio | Alto | 🔴 Crítico |
| 10.3 | Corregir `requirements.txt` | Bajo | Alto | 🟠 Alto |
| 10.4 | Centralizar config en `config.py` | Medio | Alto | 🟠 Alto |
| 10.5 | Eliminar código duplicado con `utils.py` | Medio | Medio | 🟠 Alto |
| 10.6 | Corregir tests T02 y T09 | Medio | Medio | 🟡 Medio |
| 10.7 | Separar caché vectorstore / chain | Bajo | Medio | 🟡 Medio |
| 10.8 | Agregar type hints | Bajo | Medio | 🟡 Medio |
| 10.9 | Validar input del usuario | Bajo | Medio | 🟡 Medio |
| 10.10 | Reintentos en llamadas API | Medio | Medio | 🟡 Medio |
| 10.11 | Reemplazar print() con logging | Bajo | Bajo | 🟢 Bajo |
| 10.12 | Implementar botón Exportar | Medio | Bajo | 🟢 Bajo |
| 10.13 | Tests unitarios para parsear_respuesta() | Medio | Medio | 🟡 Medio |
| 10.14 | GitHub Actions CI/CD | Medio | Medio | 🟡 Medio |

---

*Documento generado a partir del análisis del código fuente del proyecto — Ingeniería de Soluciones con IA, DuocUC 2026.*
