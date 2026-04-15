import os
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

load_dotenv()

VECTORSTORE_DIR = "vectorstore"

st.set_page_config(
    page_title="Asistente Tributario - Ruiz Salazar",
    page_icon="⚖️",
    layout="wide"
)

# ── PROMPT ──────────────────────────────────────────────────
SYSTEM_PROMPT = """Eres un asistente de consultas tributarias del estudio Ruiz Salazar Tributaria.
Respondes preguntas sobre normativa tributaria chilena basándote en los fragmentos normativos entregados.

Reglas:
- Analiza los fragmentos entregados y extrae la información relevante para responder.
- Cita el artículo, circular o resolución exacta cuando esté disponible en el contexto.
- Si puedes inferir una respuesta parcial, entrégala indicando sus limitaciones.
- Solo si el contexto es completamente irrelevante para la pregunta, responde:
  "La normativa disponible no cubre esta consulta. Consulte directamente con un profesional."
- No inventes normas ni artículos que no aparezcan en el contexto.
- Responde en español formal.

Contexto normativo recuperado:
{context}

Pregunta: {question}

Respuesta:"""

prompt = PromptTemplate(
    template=SYSTEM_PROMPT,
    input_variables=["context", "question"]
)

# ── CARGA DEL MODELO (cached) ────────────────────────────────
@st.cache_resource
def cargar_chain():
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        base_url="https://models.inference.ai.azure.com",
        api_key=os.getenv("GITHUB_TOKEN")
    )
    vectorstore = FAISS.load_local(
        VECTORSTORE_DIR,
        embeddings,
        allow_dangerous_deserialization=True
    )
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        base_url="https://models.inference.ai.azure.com",
        api_key=os.getenv("GITHUB_TOKEN")
    )
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 4}
    )
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )
    return chain

# ── INTERFAZ ─────────────────────────────────────────────────
st.title("⚖️ Asistente Tributario")
st.caption("Ruiz Salazar Tributaria — consulta normativa con citación de fuente")

# Sidebar
st.sidebar.header("⚙️ Configuración")

k_docs = st.sidebar.slider(
    "Fragmentos a recuperar (k):",
    min_value=1, max_value=8, value=4
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Corpus disponible**")
st.sidebar.markdown("""
- DL 824 — Ley de Renta
- DL 825 — Ley de IVA
- Circulares SII
- Código Tributario
""")

st.sidebar.markdown("---")
st.sidebar.warning(
    "⚠️ Este asistente no reemplaza asesoría tributaria profesional. "
    "Las respuestas son orientativas y deben ser validadas por un contador o abogado tributario."
)

# Historial en session state
if "historial" not in st.session_state:
    st.session_state.historial = []

# Layout principal
col1, col2 = st.columns([1.2, 1])

with col1:
    st.subheader("💬 Consulta")

    consulta = st.text_area(
        "Ingresa tu consulta tributaria:",
        height=120,
        placeholder="Ej: ¿Qué actividades están exentas de IVA según el artículo 12 del DL 825?"
    )

    consultar_btn = st.button("🔍 Consultar", type="primary", use_container_width=True)

    if consultar_btn and consulta.strip():
        with st.spinner("Buscando en la normativa..."):
            try:
                chain = cargar_chain()
                # Actualizar k dinámicamente
                chain.retriever.search_kwargs["k"] = k_docs
                resultado = chain.invoke({"query": consulta})

                respuesta = resultado["result"]
                fuentes = resultado["source_documents"]

                # Guardar en historial
                st.session_state.historial.append({
                    "consulta": consulta,
                    "respuesta": respuesta,
                    "fuentes": fuentes
                })

            except Exception as e:
                st.error(f"Error al procesar la consulta: {e}")

    elif consultar_btn:
        st.warning("Ingresa una consulta antes de continuar.")

    # Mostrar última respuesta
    if st.session_state.historial:
        ultimo = st.session_state.historial[-1]

        st.subheader("📋 Respuesta")
        st.markdown(ultimo["respuesta"])

        st.subheader("📎 Fuentes consultadas")
        for i, doc in enumerate(ultimo["fuentes"], 1):
            fuente = doc.metadata.get("source", "desconocida")
            pagina = doc.metadata.get("page", "?")
            nombre = os.path.basename(fuente)
            with st.expander(f"Fragmento {i} — {nombre}, pág. {pagina}"):
                st.caption(doc.page_content)

with col2:
    st.subheader("🕓 Historial de consultas")

    if not st.session_state.historial:
        st.info("Las consultas realizadas aparecerán aquí.")
    else:
        for i, item in enumerate(reversed(st.session_state.historial), 1):
            with st.expander(f"Consulta {len(st.session_state.historial) - i + 1}: {item['consulta'][:60]}..."):
                st.markdown(f"**Pregunta:** {item['consulta']}")
                st.markdown(f"**Respuesta:** {item['respuesta']}")

    if st.session_state.historial:
        if st.button("🗑️ Limpiar historial", use_container_width=True):
            st.session_state.historial = []
            st.rerun()