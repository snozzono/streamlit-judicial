import json
import logging
import os

import streamlit as st
from dotenv import load_dotenv
from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_core.messages import AIMessage, HumanMessage

from config import CONFIG, VECTORSTORE_FILES
from graph import crear_grafo
from memory import get_memoria_largo_plazo, nueva_sesion
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

API_KEY = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

if not API_KEY:
    st.set_page_config(page_title="Error — Asistente Tributario", page_icon="❌")
    st.error("❌ GH_TOKEN no encontrado en variables de entorno. Revisa tu archivo .env.")
    st.stop()

st.set_page_config(
    page_title="Asistente Tributario — Ruiz Salazar",
    page_icon="⚖️",
    layout="wide",
)


# ── RECURSOS CACHEADOS ────────────────────────────────────────────────────────

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
                "Vuelve a ejecutar `python indexar.py`."
            )
    return True, ""


@st.cache_resource
def cargar_vectorstore():
    ok, msg = validar_vectorstore()
    if not ok:
        st.error(f"❌ {msg}")
        st.stop()
    try:
        embeddings = get_embeddings(API_KEY)
        vs = FAISS.load_local(
            CONFIG.vectorstore_dir,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        logger.info("Vectorstore cargado correctamente.")
        return vs
    except Exception as exc:
        err = str(exc)
        if "Invalid index file" in err or "read failed" in err.lower():
            st.error(
                "❌ El índice FAISS no es compatible. "
                "Borra 'vectorstore/' y vuelve a ejecutar `python indexar.py`."
            )
        else:
            st.error(f"❌ Error al cargar el vectorstore: {err}")
        st.stop()


@st.cache_resource
def cargar_chain(k: int, temperature: float) -> RetrievalQA:
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


@st.cache_resource
def cargar_grafo():
    return crear_grafo()


@st.cache_resource
def cargar_memoria_lp():
    return get_memoria_largo_plazo()


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

st.sidebar.header("⚙️ Configuración")

k_docs = st.sidebar.slider(
    "Fragmentos a recuperar (k):",
    min_value=1,
    max_value=8,
    value=CONFIG.k_default,
    help="Más fragmentos = más contexto disponible para el modelo.",
)

temperatura = st.sidebar.slider(
    "Temperatura del modelo:",
    min_value=0.0,
    max_value=1.0,
    value=CONFIG.temperature_default,
    step=0.05,
    help="Valores bajos (0.0–0.2) producen respuestas más precisas.",
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


# ── TABS ──────────────────────────────────────────────────────────────────────

tab_ep2, tab_ep1 = st.tabs(["💬 Conversacional (EP2)", "🔍 Consulta clásica (EP1)"])


# ════════════════════════════════════════════════════════════════════════════
# TAB EP2 — Interfaz conversacional con LangGraph
# ════════════════════════════════════════════════════════════════════════════

with tab_ep2:

    # — Session state EP2 —
    if "mensajes_ep2" not in st.session_state:
        st.session_state.mensajes_ep2 = []       # [{"rol": "usuario"|"asistente", "contenido": str, "ruta_memo": str|None}]
    if "memoria_cp" not in st.session_state:
        st.session_state.memoria_cp = nueva_sesion()
    if "sesion_cerrada" not in st.session_state:
        st.session_state.sesion_cerrada = False
    if "confirmar_memo" not in st.session_state:
        st.session_state.confirmar_memo = False
    if "ultima_ruta_memo" not in st.session_state:
        st.session_state.ultima_ruta_memo = None

    st.title("⚖️ Asistente Tributario — Ruiz Salazar")
    st.caption("EP2 · Agente conversacional con LangGraph · DL-824 / DL-825 / DL-830")

    # — Botones de sesión —
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

    with col_btn1:
        if st.button("📝 Generar memo", disabled=st.session_state.sesion_cerrada):
            st.session_state.confirmar_memo = True

    with col_btn2:
        if st.button("🔒 Cerrar sesión", disabled=st.session_state.sesion_cerrada):
            historial_texto = st.session_state.memoria_cp.obtener_historial_texto()
            if historial_texto:
                with st.spinner("Persistiendo sesión en memoria de largo plazo..."):
                    try:
                        cargar_memoria_lp().persistir_caso(
                            historial_texto,
                            metadata={"modo": "conversacional", "turnos": len(st.session_state.mensajes_ep2)},
                        )
                        st.session_state.sesion_cerrada = True
                        st.success("✅ Sesión persistida correctamente.")
                    except Exception as exc:
                        st.error(f"❌ Error al persistir sesión: {exc}")
            else:
                st.info("La sesión está vacía, no hay nada que persistir.")

    with col_btn3:
        if st.session_state.sesion_cerrada:
            if st.button("🔄 Nueva sesión"):
                st.session_state.mensajes_ep2 = []
                st.session_state.memoria_cp = nueva_sesion()
                st.session_state.sesion_cerrada = False
                st.session_state.confirmar_memo = False
                st.session_state.ultima_ruta_memo = None
                st.rerun()

    st.markdown("---")

    # — Confirmación de memo (antes de mostrar historial) —
    if st.session_state.confirmar_memo:
        st.warning("¿Confirmar la generación del memorándum con el historial actual?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Confirmar memo"):
                historial = st.session_state.memoria_cp.obtener_historial_texto()
                if not historial:
                    st.error("❌ No hay historial de consultas para generar el memo.")
                    st.session_state.confirmar_memo = False
                else:
                    with st.spinner("Generando memorándum..."):
                        try:
                            import tools as tool_fns
                            from langchain_openai import ChatOpenAI
                            from langchain_core.messages import SystemMessage, HumanMessage as HM

                            llm = ChatOpenAI(
                                model=CONFIG.llm_model,
                                base_url=CONFIG.api_base_url,
                                api_key=API_KEY,
                                temperature=0.1,
                            )
                            system = (
                                "Eres el asistente tributario de Ruiz Salazar Tributaria. "
                                "Redacta un análisis jurídico-tributario completo basado en el "
                                "historial de consultas de la sesión."
                            )
                            resp = llm.invoke([
                                SystemMessage(content=system),
                                HM(content=f"Historial de la sesión:\n\n{historial}\n\nRedacta el análisis:"),
                            ])
                            analisis = resp.content
                            ruta = tool_fns.redactar_memo(
                                caso=f"Sesión completa — {len(st.session_state.mensajes_ep2)} turnos",
                                contexto="Ver historial adjunto.",
                                analisis=analisis,
                                destinatario="Cliente",
                            )
                            st.session_state.ultima_ruta_memo = ruta
                            st.session_state.mensajes_ep2.append({
                                "rol": "asistente",
                                "contenido": f"Memorándum generado correctamente: `{ruta}`",
                                "ruta_memo": ruta,
                            })
                            st.session_state.confirmar_memo = False
                            st.success(f"✅ Memo generado: `{ruta}`")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"❌ Error al generar memo: {exc}")
        with c2:
            if st.button("❌ Cancelar"):
                st.session_state.confirmar_memo = False
                st.rerun()

    # — Descarga del memorándum —
    if st.session_state.ultima_ruta_memo and not st.session_state.confirmar_memo:
        ruta_memo = st.session_state.ultima_ruta_memo
        try:
            with open(ruta_memo, "rb") as f:
                datos_memo = f.read()
            st.download_button(
                label="⬇️ Descargar memorándum (.docx)",
                data=datos_memo,
                file_name=os.path.basename(ruta_memo),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=False,
            )
        except Exception as exc:
            st.warning(f"No se pudo leer el memo: {exc}")

    st.markdown("---")

    # — Historial del chat —
    for msg in st.session_state.mensajes_ep2:
        rol_st = "user" if msg["rol"] == "usuario" else "assistant"
        with st.chat_message(rol_st):
            st.markdown(msg["contenido"])
            if msg.get("ruta_memo"):
                st.caption(f"📄 Memo: `{msg['ruta_memo']}`")

    # — Input conversacional —
    if not st.session_state.sesion_cerrada:
        consulta_raw = st.chat_input("Escribe tu consulta tributaria...")

        if consulta_raw:
            try:
                consulta = validar_consulta(consulta_raw)
            except ValueError as exc:
                st.warning(f"⚠️ {exc}")
                consulta = ""

            if consulta:
                # Mostrar mensaje del usuario
                st.session_state.mensajes_ep2.append({"rol": "usuario", "contenido": consulta, "ruta_memo": None})
                with st.chat_message("user"):
                    st.markdown(consulta)

                # Invocar el grafo
                with st.chat_message("assistant"):
                    with st.spinner("Analizando normativa..."):
                        try:
                            grafo = cargar_grafo()
                            historial_lc = st.session_state.memoria_cp.obtener_historial()

                            estado_entrada = {
                                "consulta": consulta,
                                "historial_mensajes": historial_lc,
                                "chunks_normativa": [],
                                "casos_similares": [],
                                "contexto_acumulado": "",
                                "evaluacion": {},
                                "iteraciones": 0,
                                "modo": "responder",
                                "respuesta": "",
                                "ruta_memo": None,
                            }

                            estado_final = grafo.invoke(estado_entrada)
                            respuesta = estado_final.get("respuesta", "No se pudo generar una respuesta.")
                            ruta_memo = estado_final.get("ruta_memo")

                            st.markdown(respuesta)
                            if ruta_memo:
                                st.success(f"📄 Memorándum generado: `{ruta_memo}`")
                                st.session_state.ultima_ruta_memo = ruta_memo

                        except Exception as exc:
                            logger.error("Error en grafo: %s", exc)
                            st.error(f"❌ Error al procesar la consulta: {exc}")
                            respuesta = f"Error: {exc}"
                            ruta_memo = None

                # Actualizar memoria de corto plazo
                st.session_state.memoria_cp.agregar_turno(consulta, respuesta)
                st.session_state.mensajes_ep2.append({
                    "rol": "asistente",
                    "contenido": respuesta,
                    "ruta_memo": ruta_memo,
                })
    else:
        st.info("🔒 Sesión cerrada. Inicia una nueva sesión para continuar.")


# ════════════════════════════════════════════════════════════════════════════
# TAB EP1 — Consulta clásica (sin cambios respecto a EP1)
# ════════════════════════════════════════════════════════════════════════════

with tab_ep1:

    st.title("⚖️ Asistente Tributario")
    st.caption("Ruiz Salazar Tributaria — consulta normativa con citación de fuente")

    if "historial" not in st.session_state:
        st.session_state.historial = []

    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.subheader("💬 Consulta")

        consulta_raw_ep1 = st.text_area(
            "Ingresa tu consulta tributaria:",
            height=120,
            placeholder="Ej: ¿Qué actividades están exentas de IVA según el artículo 12 del DL 825?",
            key="consulta_ep1",
        )

        consultar_btn = st.button("🔍 Consultar", type="primary", use_container_width=True, key="btn_ep1")

        if consultar_btn:
            try:
                consulta_ep1 = validar_consulta(consulta_raw_ep1)
            except ValueError as exc:
                st.warning(f"⚠️ {exc}")
                consulta_ep1 = ""

            if consulta_ep1:
                with st.spinner("Buscando en la normativa..."):
                    try:
                        chain = cargar_chain(k_docs, temperatura)
                        resultado = llamar_con_reintento(chain, consulta_ep1)
                        respuesta_raw = resultado["result"]
                        fuentes = resultado["source_documents"]
                        secciones = parsear_respuesta(respuesta_raw)

                        st.session_state.historial.append(
                            {
                                "consulta": consulta_ep1,
                                "respuesta_raw": respuesta_raw,
                                "secciones": secciones,
                                "fuentes": fuentes,
                                "k_usado": k_docs,
                                "temperatura": temperatura,
                            }
                        )
                        logger.info("Consulta EP1 procesada con %d fragmentos.", len(fuentes))
                        st.success(f"✅ Procesada con {len(fuentes)} fragmentos relevantes")

                    except Exception as exc:
                        logger.error("Error EP1: %s", exc)
                        st.error(f"❌ Error al procesar la consulta: {exc}")

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
                if st.button("🗑️ Limpiar", use_container_width=True, key="limpiar_ep1"):
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
                    key="export_ep1",
                )