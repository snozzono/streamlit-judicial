"""
graph.py — Grafo LangGraph del agente tributario.

Topología:
    START → classifier
    classifier → buscar_normativa + buscar_casos (paralelo, Send)
    buscar_normativa → evaluar_consulta
    buscar_casos     → evaluar_consulta
    evaluar_consulta → razonador | responder | redactar_memo  (condicional)
    razonador        → evaluar_consulta                       (loop ≤ max_iterations)
    responder        → persistir → END
    redactar_memo    → persistir → END

Función pública: crear_grafo() → CompiledGraph
"""

import os
from operator import add
from typing import Annotated, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

import tools as tool_fns
from config import CONFIG


# ---------------------------------------------------------------------------
# Estado del agente
# ---------------------------------------------------------------------------

class EstadoAgente(TypedDict):
    consulta: str
    historial_mensajes: Annotated[list[BaseMessage], add]   # acumula entre turnos
    chunks_normativa: list
    casos_similares: list
    contexto_acumulado: str
    evaluacion: dict
    iteraciones: int
    modo: str           # "responder" | "memo"
    respuesta: str
    ruta_memo: Optional[str]


# ---------------------------------------------------------------------------
# LLM compartido
# ---------------------------------------------------------------------------

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=CONFIG.llm_model,
        base_url=CONFIG.api_base_url,
        api_key=os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN") or "",
        temperature=0.1,
    )


# ---------------------------------------------------------------------------
# Nodos
# ---------------------------------------------------------------------------

def nodo_classifier(state: EstadoAgente) -> dict:
    """Determina el modo de respuesta según la intención de la consulta."""
    consulta_lower = state["consulta"].lower()
    indicadores_memo = {"memo", "memorándum", "memorandum", "informe formal", "redactar", "documento formal"}
    modo = "memo" if any(ind in consulta_lower for ind in indicadores_memo) else "responder"
    return {"modo": modo, "iteraciones": 0}


def nodo_buscar_normativa(state: EstadoAgente) -> dict:
    """Recupera fragmentos del vectorstore de normativa tributaria."""
    chunks = tool_fns.buscar_normativa(state["consulta"], k=CONFIG.k_default)
    return {"chunks_normativa": chunks}


def nodo_buscar_casos(state: EstadoAgente) -> dict:
    """Recupera casos anteriores similares del índice de largo plazo."""
    casos = tool_fns.buscar_casos_anteriores(state["consulta"], k=3)
    return {"casos_similares": casos}


def nodo_evaluar_consulta(state: EstadoAgente) -> dict:
    """Evalúa si el contexto acumulado es suficiente para responder."""
    chunks_texto = "\n\n".join(c.page_content for c in state.get("chunks_normativa", []))
    casos_texto = "\n\n".join(c.page_content for c in state.get("casos_similares", []))

    # Si ya hay contexto acumulado (iteraciones > 0), preservarlo y expandirlo
    base = state.get("contexto_acumulado") or ""
    nuevo_contexto = f"{chunks_texto}\n\n{casos_texto}".strip()
    contexto = (base + "\n\n" + nuevo_contexto).strip() if base else nuevo_contexto

    evaluacion = tool_fns.evaluar_consulta(state["consulta"], contexto)
    return {"evaluacion": evaluacion, "contexto_acumulado": contexto}


def nodo_razonador(state: EstadoAgente) -> dict:
    """
    Refina la búsqueda con una consulta más específica.
    Se ejecuta en loop hasta confianza >= umbral o iteraciones == max.
    """
    llm = _get_llm()
    confianza_actual = state["evaluacion"].get("confianza", 0)

    system = (
        "Eres un razonador tributario experto. Analiza la consulta y el contexto disponible "
        "para formular una consulta de búsqueda más específica que encuentre la normativa faltante. "
        "Responde SOLO con la nueva consulta de búsqueda (una sola línea, sin explicaciones)."
    )
    user = (
        f"Consulta original: {state['consulta']}\n\n"
        f"Confianza actual: {confianza_actual:.0%}\n\n"
        f"Contexto disponible (fragmento):\n{state['contexto_acumulado'][:1500]}\n\n"
        "Nueva consulta de búsqueda refinada:"
    )

    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    consulta_refinada = resp.content.strip()

    # Búsqueda adicional con la consulta refinada
    chunks_extra = tool_fns.buscar_normativa(consulta_refinada, k=4)
    texto_extra = "\n\n".join(c.page_content for c in chunks_extra)
    contexto_expandido = (
        state["contexto_acumulado"]
        + "\n\n--- Búsqueda refinada ---\n\n"
        + texto_extra
    )

    nueva_evaluacion = tool_fns.evaluar_consulta(state["consulta"], contexto_expandido)

    return {
        "contexto_acumulado": contexto_expandido,
        "evaluacion": nueva_evaluacion,
        "iteraciones": state["iteraciones"] + 1,
        "chunks_normativa": chunks_extra,
    }


_SYSTEM_RESPONDER = """Eres el asistente tributario de Ruiz Salazar Tributaria.
Respondes consultas sobre normativa tributaria chilena (DL-824, DL-825, DL-830 y circulares SII).

Estructura tu respuesta SIEMPRE con estos encabezados exactos:

## Análisis
<respuesta detallada citando artículos concretos>

## Artículos citados
<lista de artículos mencionados, uno por línea>

## Limitaciones
<aspectos no cubiertos o fuera del alcance de la normativa disponible>

Responde en español formal y lenguaje técnico-jurídico. No inventes normas."""


def nodo_responder(state: EstadoAgente) -> dict:
    """Genera la respuesta final estructurada."""
    llm = _get_llm()

    historial_texto = "\n".join(
        f"{'Usuario' if m.type == 'human' else 'Agente'}: {m.content}"
        for m in state.get("historial_mensajes", [])[-6:]
    )

    user = (
        f"Historial de la sesión:\n{historial_texto}\n\n"
        f"Consulta actual: {state['consulta']}\n\n"
        f"Contexto normativo disponible:\n{state['contexto_acumulado'][:3000]}\n\n"
        "Respuesta:"
    )

    resp = llm.invoke([SystemMessage(content=_SYSTEM_RESPONDER), HumanMessage(content=user)])
    return {"respuesta": resp.content}


def nodo_redactar_memo(state: EstadoAgente) -> dict:
    """Genera el análisis y produce el memorándum .docx."""
    llm = _get_llm()

    system = (
        "Eres el asistente tributario de Ruiz Salazar Tributaria. "
        "Redacta un análisis jurídico-tributario completo y formal para incluir en un memorándum oficial."
    )
    user = (
        f"Consulta: {state['consulta']}\n\n"
        f"Contexto normativo:\n{state['contexto_acumulado'][:3000]}\n\n"
        "Redacta el análisis completo:"
    )
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    analisis = resp.content

    ruta = tool_fns.redactar_memo(
        caso=state["consulta"],
        contexto=state["contexto_acumulado"][:1500],
        analisis=analisis,
        destinatario="Cliente",
    )

    resumen = f"Memorándum generado: `{ruta}`\n\n{analisis}"
    return {"respuesta": resumen, "ruta_memo": ruta}


def nodo_persistir(state: EstadoAgente) -> dict:
    """Paso final: no-op durante consultas normales.
    La persistencia real se dispara desde app.py al cerrar sesión."""
    return {}


# ---------------------------------------------------------------------------
# Aristas condicionales
# ---------------------------------------------------------------------------

def _router_classifier(state: EstadoAgente):
    """Fan-out paralelo: ejecuta búsqueda de normativa y casos simultáneamente."""
    return [
        Send("buscar_normativa", state),
        Send("buscar_casos", state),
    ]


def _router_post_eval(state: EstadoAgente) -> str:
    """Decide el siguiente nodo según la confianza y el modo."""
    confianza = state.get("evaluacion", {}).get("confianza", 1.0)
    iteraciones = state.get("iteraciones", 0)

    if confianza < CONFIG.confianza_minima and iteraciones < CONFIG.max_reasoning_iterations:
        return "razonador"
    if state.get("modo") == "memo":
        return "redactar_memo"
    return "responder"


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def crear_grafo():
    """Construye y compila el grafo LangGraph del agente tributario.

    Returns:
        CompiledGraph listo para invocar.
    """
    builder = StateGraph(EstadoAgente)

    # — Nodos —
    builder.add_node("classifier", nodo_classifier)
    builder.add_node("buscar_normativa", nodo_buscar_normativa)
    builder.add_node("buscar_casos", nodo_buscar_casos)
    builder.add_node("evaluar_consulta", nodo_evaluar_consulta)
    builder.add_node("razonador", nodo_razonador)
    builder.add_node("responder", nodo_responder)
    builder.add_node("redactar_memo", nodo_redactar_memo)
    builder.add_node("persistir", nodo_persistir)

    # — Aristas —
    builder.add_edge(START, "classifier")

    # Fan-out paralelo desde classifier
    builder.add_conditional_edges("classifier", _router_classifier)

    # Fan-in: ambas búsquedas confluyen en evaluar_consulta
    builder.add_edge("buscar_normativa", "evaluar_consulta")
    builder.add_edge("buscar_casos", "evaluar_consulta")

    # Arista condicional post-evaluación
    builder.add_conditional_edges(
        "evaluar_consulta",
        _router_post_eval,
        ["razonador", "responder", "redactar_memo"],
    )

    # Loop del razonador
    builder.add_edge("razonador", "evaluar_consulta")

    # Nodos terminales → persistir → END
    builder.add_edge("responder", "persistir")
    builder.add_edge("redactar_memo", "persistir")
    builder.add_edge("persistir", END)

    return builder.compile()