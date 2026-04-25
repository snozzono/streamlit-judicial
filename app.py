import json
import logging
import os

import streamlit as st
from dotenv import load_dotenv
from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import FAISS

from config import CONFIG, VECTORSTORE_FILES
from utils import (
    get_embeddings,
    get_llm,
    get_prompt_template,
    llamar_con_reintento,
    parsear_respuesta,
    validar_consulta,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

API_KEY = os.getenv("GITHUB_TOKEN")

# Validación temprana: set_page_config debe ir antes de cualquier otro st.*
if not API_KEY:
    st.set_page_config(page_title="Error — Asistente Tributario", page_icon="❌")
    st.error("❌ GITHUB_TOKEN no encontrado en variables de entorno. Revisa tu archivo .env.")
    st.stop()

st.set_page_config(
    page_title="Asistente Tributario — Ruiz Salazar",
    page_icon="⚖️",
    layout="wide",
)


# ── VALIDACIÓN DEL VECTORSTORE ────────────────────────────────────────────────
def validar_vectorstore() -> tuple[bool, str]:
    if not os.path.exists(CONFIG.vectorstore_dir):
        return False, (
            f"El directorio '{CONFIG.vectorstore_dir}/' no existe. "
            "Ejecuta `python indexar.py` para generar el índice."
        )
    for fname in VECTORSTORE_FILES:
        fpath = os.path.join(CONFIG.vectorstore_dir, fname)
        if not os.path.exists(fpath):
            return False, (
                f"Archivo '{fname}' no encontrado en '{CONFIG.vectorstore_dir}/'. "
                "El vectorstore puede estar incompleto. Vuelve a ejecutar `python indexar.py`."
            )
    return True, ""


# ── CARGA CACHEADA ────────────────────────────────────────────────────────────
@st.cache_resource
def cargar_vectorstore():
    """Carga el vectorstore una sola vez por sesión; no depende de k ni temperatura."""
    ok, msg = validar_vectorstore()
    if not ok:
        st.error(f"❌ {msg}")
        st.stop()

    try:
        embeddings = get_embeddings(API_KEY)
        vectorstore = FAISS.load_local(
            CONFIG.vectorstore_dir,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info("Vectorstore cargado correctamente.")
        return vectorstore
    except Exception as exc:
        err = str(exc)
        if "Invalid index file" in err or "read failed" in err.lower():
            st.error(
                "❌ El índice FAISS no es compatible con la versión instalada. "
                "Borra 'vectorstore/' y vuelve a ejecutar `python indexar.py`."
            )
        else:
            st.error(f"❌ Error al cargar el vectorstore: {err}")
        st.stop()


@st.cache_resource
def cargar_chain(k: int, temperature: float) -> RetrievalQA:
    """Construye la cadena para la combinación (k, temperature); se recrea solo al cambiar los sliders."""
    vectorstore = cargar_vectorstore()
    llm = get_llm(API_KEY, temperature)
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": get_prompt_template()},
        return_source_documents=True,
    )


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("⚖️ Asistente Tributario")
st.caption("Ruiz Salazar Tributaria — consulta normativa con citación de fuente")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Configuración")

k_docs = st.sidebar.slider(
    "Fragmentos a recuperar (k):",
    min_value=1,
    max_value=8,
    value=CONFIG.k_default,
    help="Más fragmentos = más contexto disponible para el modelo, respuestas más completas.",
)

temperatura = st.sidebar.slider(
    "Temperatura del modelo:",
    min_value=0.0,
    max_value=1.0,
    value=CONFIG.temperature_default,
    step=0.05,
    help="Valores bajos (0.0–0.2) producen respuestas más precisas. "
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

# ── LAYOUT ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("💬 Consulta")

    consulta_raw = st.text_area(
        "Ingresa tu consulta tributaria:",
        height=120,
        placeholder="Ej: ¿Qué actividades están exentas de IVA según el artículo 12 del DL 825?",
    )

    consultar_btn = st.button("🔍 Consultar", type="primary", use_container_width=True)

    if consultar_btn:
        try:
            consulta = validar_consulta(consulta_raw)
        except ValueError as exc:
            st.warning(f"⚠️ {exc}")
            consulta = ""

        if consulta:
            with st.spinner("Buscando en la normativa..."):
                try:
                    chain = cargar_chain(k_docs, temperatura)
                    resultado = llamar_con_reintento(chain, consulta)
                    respuesta_raw = resultado["result"]
                    fuentes = resultado["source_documents"]
                    secciones = parsear_respuesta(respuesta_raw)

                    st.session_state.historial.append(
                        {
                            "consulta": consulta,
                            "respuesta_raw": respuesta_raw,
                            "secciones": secciones,
                            "fuentes": fuentes,
                            "k_usado": k_docs,
                            "temperatura": temperatura,
                        }
                    )
                    logger.info("Consulta procesada con %d fragmentos.", len(fuentes))
                    st.success(f"✅ Procesada con {len(fuentes)} fragmentos relevantes")

                except Exception as exc:
                    logger.error("Error al procesar consulta: %s", exc)
                    st.error(f"❌ Error al procesar la consulta: {exc}")

    # ── ÚLTIMA RESPUESTA ──────────────────────────────────────────────────────
    if st.session_state.historial:
        ultimo = st.session_state.historial[-1]
        secs = ultimo["secciones"]

        st.subheader("📋 Respuesta")

        if secs["analisis"]:
            st.markdown("**Análisis**")
            st.markdown(secs["analisis"])

        if secs["articulos"]:
            st.markdown("**Artículos citados**")
            for linea in secs["articulos"].splitlines():
                if linea.strip():
                    st.markdown(f"- {linea.strip()}")

        if secs["limitaciones"]:
            st.info(f"⚠️ **Limitaciones:** {secs['limitaciones']}")

        st.subheader(f"📎 Fuentes ({len(ultimo['fuentes'])} fragmentos)")
        for i, doc in enumerate(ultimo["fuentes"], 1):
            fuente = doc.metadata.get("source", "desconocida")
            pagina = doc.metadata.get("page", "?")
            nombre = os.path.basename(fuente)
            with st.expander(f"Fragmento {i} — {nombre}, pág. {pagina}"):
                st.caption(doc.page_content)

# ── HISTORIAL ─────────────────────────────────────────────────────────────────
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
                    f"📊 k={item.get('k_usado', CONFIG.k_default)} · "
                    f"temp={item.get('temperatura', CONFIG.temperature_default)}"
                )

    st.markdown("---")
    if st.session_state.historial:
        col_clear, col_export = st.columns(2)

        with col_clear:
            if st.button("🗑️ Limpiar", use_container_width=True):
                st.session_state.historial = []
                st.rerun()

        with col_export:
            exportable = [
                {
                    "consulta": item["consulta"],
                    "analisis": item["secciones"]["analisis"],
                    "articulos": item["secciones"]["articulos"],
                    "limitaciones": item["secciones"]["limitaciones"],
                    "k_usado": item.get("k_usado"),
                    "temperatura": item.get("temperatura"),
                }
                for item in st.session_state.historial
            ]
            st.download_button(
                label="📥 Exportar",
                data=json.dumps(exportable, ensure_ascii=False, indent=2),
                file_name="historial.json",
                mime="application/json",
                use_container_width=True,
            )
