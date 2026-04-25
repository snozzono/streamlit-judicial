import logging
import time

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import RateLimitError

from config import CONFIG

logger = logging.getLogger(__name__)

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

Estructura tu respuesta SIEMPRE con estos tres encabezados exactos (no omitas ninguno):

## Análisis
<desarrollo completo de la respuesta, citando artículos en el texto>

## Artículos citados
<lista de artículos mencionados en el análisis, uno por línea; si la consulta está fuera del corpus escribe "No aplica">

## Limitaciones
<Si la respuesta está basada en el corpus: indica qué aspectos quedan fuera del contexto recuperado o qué normativa podría complementarla. Si la consulta NO es de naturaleza tributaria chilena o no está cubierta por DL-824, DL-825 ni DL-830: indica explícitamente que el tema está fuera del alcance de este asistente y recomienda consultar al organismo competente.>

Contexto normativo recuperado:
{context}

Pregunta: {question}

Respuesta:"""


def get_prompt_template() -> PromptTemplate:
    return PromptTemplate(template=SYSTEM_PROMPT, input_variables=["context", "question"])


def parsear_respuesta(texto: str) -> dict[str, str]:
    """Extrae las tres secciones del prompt estructurado devuelto por el LLM."""
    secciones: dict[str, str] = {"analisis": "", "articulos": "", "limitaciones": ""}
    marcadores = {
        "## Análisis": "analisis",
        "## Artículos citados": "articulos",
        "## Limitaciones": "limitaciones",
    }

    seccion_actual: str | None = None
    buffer: list[str] = []

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

    # Fallback: si el modelo no respetó los marcadores
    if not any(secciones.values()):
        secciones["analisis"] = texto.strip()

    return secciones


def get_embeddings(api_key: str) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=CONFIG.embedding_model,
        base_url=CONFIG.api_base_url,
        api_key=api_key,
    )


def get_llm(api_key: str, temperature: float) -> ChatOpenAI:
    return ChatOpenAI(
        model=CONFIG.llm_model,
        temperature=temperature,
        base_url=CONFIG.api_base_url,
        api_key=api_key,
    )


def validar_consulta(texto: str) -> str:
    texto = texto.strip()
    if not texto:
        raise ValueError("La consulta no puede estar vacía.")
    if len(texto) > CONFIG.max_query_length:
        raise ValueError(f"La consulta excede el máximo de {CONFIG.max_query_length} caracteres.")
    return texto


def llamar_con_reintento(chain, consulta: str, max_intentos: int = 3) -> dict:
    for intento in range(max_intentos):
        try:
            return chain.invoke({"query": consulta})
        except RateLimitError:
            if intento < max_intentos - 1:
                espera = 2 ** intento
                logger.warning("Rate limit alcanzado. Reintentando en %ds...", espera)
                time.sleep(espera)
            else:
                raise
