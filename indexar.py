import os
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

load_dotenv()

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────────
VECTORSTORE_DIR = "vectorstore"
# Archivos que FAISS.save_local() siempre genera; su ausencia indica que
# indexar.py no se ejecutó o que el directorio está corrupto.
VECTORSTORE_FILES = ["index.faiss", "index.pkl"]

API_KEY = os.getenv("GITHUB_TOKEN")

# La temperatura se expone también en el sidebar, pero se define aquí el
# valor que se usará al construir el LLM (se pasa dinámicamente, ver más abajo).
DEFAULT_TEMPERATURE = 0.1
DEFAULT_K = 8

EMBEDDINGS_CONFIG = {
    "model": "text-embedding-3-small",
    "base_url": "https://models.inference.ai.azure.com",
    "api_key": API_KEY,
}

# ── VALIDACIÓN TEMPRANA DE API KEY ───────────────────────────────────────────
# Se valida antes de set_page_config para evitar que Streamlit renderice
# una página vacía si falta el token.
if not API_KEY:
    st.set_page_config(page_title="Error — Asistente Tributario", page_icon="❌")
    st.error("❌ GITHUB_TOKEN no encontrado en variables de entorno. Revisa tu archivo .env.")
    st.stop()

st.set_page_config(
    page_title="Asistente Tributario — Ruiz Salazar",
    page_icon="⚖️",
    layout="wide",
)

# ── PROMPT ESTRUCTURADO ──────────────────────────────────────────────────────
# La respuesta se divide en tres secciones delimitadas con encabezados fijos.
# Esto permite parsear la respuesta en la UI y mostrar cada sección por separado,
# mejorando la legibilidad y facilitando la trazabilidad de las citas legales.
SYSTEM_PROMPT = """Eres un asistente de consultas tributarias del estudio Ruiz Salazar Tributaria.
Respondes preguntas sobre normativa tributaria chilena basándote en los fragmentos normativos entregados.

Reglas:
- Analiza los fragmentos entregados y extrae la información relevante para responder.
- Cita el artículo, circular o resolución exacta cuando esté disponible en el contexto.
- Si puedes inferir una respuesta parcial, entrégala indicando sus limitaciones.
- Solo si el contexto es completamente irrelevante para la pregunta, responde:
  "La normativa disponible no cubre esta consulta. Consulte directamente con un profesional."
- No inventes normas ni artículos que no aparezcan en el contexto.
- Responde en español formal y lenguaje técnico-jurídico.

Estructura tu respuesta con estos tres encabezados exactos:

## Análisis
<desarrollo completo de la respuesta, citando artículos en el texto>

## Artículos citados
<lista de artículos mencionados en el análisis, uno por línea>

## Limitaciones
<aspectos no cubiertos por el contexto, o "Ninguna" si la respuesta es completa>

Contexto normativo recuperado:
{context}

Pregunta: {question}

Respuesta:"""

prompt = PromptTemplate(
    template=SYSTEM_PROMPT,
    input_variables=["context", "question"],
)


# ── VALIDACIÓN DEL VECTORSTORE ───────────────────────────────────────────────
def validar_vectorstore() -> tuple[bool, str]:
    """
    Verifica que el directorio del vectorstore exista y que contenga los
    archivos generados por FAISS.save_local() (index.faiss e index.pkl).

    Retorna (True, "") si todo está en orden, o (False, mensaje_de_error)
    si falta el directorio o alguno de los archivos esperados.

    Separar la validación de la carga permite mostrar mensajes de error
    específicos en lugar del traceback críptico que lanza FAISS internamente.
    """
    if not os.path.exists(VECTORSTORE_DIR):
        return False, (
            f"El directorio '{VECTORSTORE_DIR}/' no existe. "
            "Ejecuta `python indexar.py` para generar el índice."
        )
    for fname in VECTORSTORE_FILES:
        fpath = os.path.join(VECTORSTORE_DIR, fname)
        if not os.path.exists(fpath):
            return False, (
                f"Archivo '{fname}' no encontrado en '{VECTORSTORE_DIR}/'. "
                "El vectorstore puede estar incompleto. Vuelve a ejecutar `python indexar.py`."
            )
    return True, ""


# ── CARGA DE MODELOS (cached) ────────────────────────────────────────────────
@st.cache_resource
def cargar_modelos() -> tuple:
    """
    Carga y cachea el vectorstore FAISS y el modelo de embeddings.
    Se separa del LLM y de la cadena para que un cambio en temperatura o k
    no fuerce a recargar el índice FAISS desde disco (operación costosa).

    Si FAISS lanza una excepción al deserializar (índice de versión
    incompatible, archivo truncado, etc.), se captura y se muestra un
    mensaje accionable en lugar del traceback interno de LangChain.
    """
    ok, msg = validar_vectorstore()
    if not ok:
        st.error(f"❌ {msg}")
        st.stop()

    try:
        embeddings = OpenAIEmbeddings(**EMBEDDINGS_CONFIG)
        vectorstore = FAISS.load_local(
            VECTORSTORE_DIR,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        return vectorstore, embeddings
    except Exception as e:
        error_str = str(e)
        # FAISS lanza errores poco descriptivos cuando el índice fue generado
        # con una versión distinta de la librería. Se detecta y se orienta al usuario.
        if "Invalid index file" in error_str or "read failed" in error_str.lower():
            st.error(
                "❌ El índice FAISS no es compatible con la versión instalada de faiss-cpu. "
                "Borra la carpeta 'vectorstore/' y vuelve a ejecutar `python indexar.py`."
            )
        else:
            st.error(f"❌ Error al cargar el vectorstore: {error_str}")
        st.stop()


@st.cache_resource
def cargar_chain(k: int, temperature: float) -> RetrievalQA:
    """
    Construye la cadena RetrievalQA para una combinación específica de k y
    temperatura. Streamlit solo reconstruye la cadena cuando alguno de estos
    parámetros cambia; el vectorstore cacheado en cargar_modelos() se reutiliza.

    Args:
        k:           Número de fragmentos a recuperar por consulta.
        temperature: Temperatura del LLM (0.0 = determinista, 1.0 = creativo).
    """
    vectorstore, _ = cargar_modelos()
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature,
        base_url="https://models.inference.ai.azure.com",
        api_key=API_KEY,
    )
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True,
    )


# ── PARSEO DE RESPUESTA ESTRUCTURADA ─────────────────────────────────────────
def parsear_respuesta(texto: str) -> dict:
    """
    Extrae las tres secciones del prompt estructurado del texto devuelto
    por el LLM. Si el modelo no respeta el formato (por ejemplo, en la
    respuesta de "normativa no disponible"), retorna el texto completo
    en 'analisis' y los demás campos vacíos.

    Args:
        texto: Respuesta cruda del LLM.

    Returns:
        Dict con claves 'analisis', 'articulos', 'limitaciones'.
    """
    secciones = {"analisis": "", "articulos": "", "limitaciones": ""}
    marcadores = {
        "## Análisis": "analisis",
        "## Artículos citados": "articulos",
        "## Limitaciones": "limitaciones",
    }

    seccion_actual = None
    buffer = []

    for linea in texto.splitlines():
        linea_strip = linea.strip()
        if linea_strip in marcadores:
            if seccion_actual:
                secciones[seccion_actual] = "\n".join(buffer).strip()
            seccion_actual = marcadores[linea_strip]
            buffer = []
        else:
            buffer.append(linea)

    if seccion_actual:
        secciones[seccion_actual] = "\n".join(buffer).strip()

    # Fallback: si no se encontró ningún marcador
    if not any(secciones.values()):
        secciones["analisis"] = texto.strip()

    return secciones


# ── INTERFAZ ──────────────────────────────────────────────────────────────────
st.title("⚖️ Asistente Tributario")
st.caption("Ruiz Salazar Tributaria — consulta normativa con citación de fuente")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Configuración")

k_docs = st.sidebar.slider(
    "Fragmentos a recuperar (k):",
    min_value=1,
    max_value=8,
    value=DEFAULT_K,
    help="Más fragmentos = más contexto disponible para el modelo, respuestas más completas.",
)

temperatura = st.sidebar.slider(
    "Temperatura del modelo:",
    min_value=0.0,
    max_value=1.0,
    value=DEFAULT_TEMPERATURE,
    step=0.05,
    help="Valores bajos (0.0–0.2) producen respuestas más precisas y reproducibles. "
         "Valores altos aumentan la variabilidad.",
)

st.sidebar.markdown("---")
st.sidebar.markdown("**📚 Corpus disponible**")
st.sidebar.markdown(
    "- DL 824 — Ley de Renta\n"
    "- DL 825 — Ley de IVA\n"
    "- DL 830 — Código Tributario"
)
st.sidebar.markdown("---")
st.sidebar.warning(
    "⚠️ Este asistente es orientativo. Las respuestas deben ser validadas "
    "por un contador o abogado tributario."
)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "historial" not in st.session_state:
    st.session_state.historial = []

# ── LAYOUT PRINCIPAL ──────────────────────────────────────────────────────────
col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("💬 Consulta")

    consulta = st.text_area(
        "Ingresa tu consulta tributaria:",
        height=120,
        placeholder="Ej: ¿Qué actividades están exentas de IVA según el artículo 12 del DL 825?",
    )

    consultar_btn = st.button("🔍 Consultar", type="primary", use_container_width=True)

    if consultar_btn and consulta.strip():
        with st.spinner("Buscando en la normativa..."):
            try:
                chain = cargar_chain(k_docs, temperatura)
                resultado = chain.invoke({"query": consulta})
                respuesta_raw = resultado["result"]
                fuentes = resultado["source_documents"]
                secciones = parsear_respuesta(respuesta_raw)

                st.session_state.historial.append({
                    "consulta": consulta,
                    "respuesta_raw": respuesta_raw,
                    "secciones": secciones,
                    "fuentes": fuentes,
                    "k_usado": k_docs,
                    "temperatura": temperatura,
                })
                st.success(f"✅ Procesada con {len(fuentes)} fragmentos relevantes")

            except Exception as e:
                st.error(f"❌ Error al procesar la consulta: {str(e)}")

    elif consultar_btn:
        st.warning("⚠️ Ingresa una consulta antes de continuar.")

    # ── MOSTRAR ÚLTIMA RESPUESTA ──────────────────────────────────────────────
    if st.session_state.historial:
        ultimo = st.session_state.historial[-1]
        secs = ultimo["secciones"]

        st.subheader("📋 Respuesta")

        if secs["analisis"]:
            st.markdown("**Análisis**")
            st.markdown(secs["analisis"])

        if secs["articulos"]:
            st.markdown("**Artículos citados**")
            # Cada línea no vacía se muestra como ítem de lista
            for linea in secs["articulos"].splitlines():
                if linea.strip():
                    st.markdown(f"- {linea.strip()}")

        if secs["limitaciones"]:
            st.info(f"⚠️ **Limitaciones:** {secs['limitaciones']}")

        # ── FUENTES ───────────────────────────────────────────────────────────
        st.subheader(f"📎 Fuentes ({len(ultimo['fuentes'])} fragmentos)")
        for i, doc in enumerate(ultimo["fuentes"], 1):
            fuente = doc.metadata.get("source", "desconocida")
            pagina = doc.metadata.get("page", "?")
            nombre = os.path.basename(fuente)
            with st.expander(f"Fragmento {i} — {nombre}, pág. {pagina}"):
                st.caption(doc.page_content)

# ── HISTORIAL ────────────────────────────────────────────────────────────────
with col2:
    st.subheader("🕓 Historial")

    if not st.session_state.historial:
        st.info("Las consultas aparecerán aquí.")
    else:
        st.metric("Total de consultas", len(st.session_state.historial))
        st.markdown("---")

        for i, item in enumerate(reversed(st.session_state.historial), 1):
            numero = len(st.session_state.historial) - i + 1
            titulo = f"**{numero}.** {item['consulta'][:50]}..."
            with st.expander(titulo):
                st.markdown(f"**Pregunta:** {item['consulta']}")
                st.markdown(item["secciones"]["analisis"] or item["respuesta_raw"])
                if item["secciones"]["articulos"]:
                    st.caption(f"📜 {item['secciones']['articulos'][:120]}...")
                st.caption(
                    f"📊 k={item.get('k_usado', DEFAULT_K)} · "
                    f"temp={item.get('temperatura', DEFAULT_TEMPERATURE)}"
                )

    st.markdown("---")
    if st.session_state.historial:
        col_clear, col_export = st.columns(2)
        with col_clear:
            if st.button("🗑️ Limpiar", use_container_width=True):
                st.session_state.historial = []
                st.rerun()
        with col_export:
            if st.button("📥 Exportar", use_container_width=True, disabled=True):
                st.info("Función en desarrollo")