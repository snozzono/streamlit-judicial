"""
anonymizer.py — Pipeline de anonimización de entidades sensibles.

Reemplaza RUTs, nombres, razones sociales, direcciones y emails
por placeholders del tipo [ENTIDAD_N] antes de persistir un caso
en el índice de largo plazo.

Flujo:
    texto -> _anonimizar_regex() -> _anonimizar_llm() -> texto anonimizado
"""

import re
import os
import json
from typing import Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import CONFIG


# ---------------------------------------------------------------------------
# Mapa de placeholders para esta sesión
# Se reinicia con cada llamada a anonimizar()
# ---------------------------------------------------------------------------
_contador: Dict[str, int] = {}
_mapa: Dict[str, str] = {}


def _reset():
    global _contador, _mapa
    _contador = {e: 0 for e in CONFIG.entidades_sensibles}
    _mapa = {}


def _placeholder(tipo: str) -> str:
    """Genera un placeholder único del tipo [EMPRESA_1], [RUT_2], etc."""
    _contador[tipo] += 1
    return f"[{tipo}_{_contador[tipo]}]"


# ---------------------------------------------------------------------------
# Paso 1: regex para patrones estructurados
# ---------------------------------------------------------------------------

# RUT chileno: 12.345.678-9 | 12345678-9 | 1.234.567-K
_RUT_PATTERN = re.compile(
    r"\b\d{1,2}\.?\d{3}\.?\d{3}-[\dKk]\b"
)

# Email
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Dirección básica (Av., Calle, Pasaje + nombre + número)
_DIRECCION_PATTERN = re.compile(
    r"\b(?:Av\.?|Avenida|Calle|Pasaje|Psje\.?|Camino)\s+[A-ZÁÉÍÓÚÑ][^\n,]{3,40}\s+\d{1,5}\b",
    re.IGNORECASE,
)


def _anonimizar_regex(texto: str) -> str:
    """Reemplaza patrones estructurados con regex."""

    def _reemplazar(match: re.Match, tipo: str) -> str:
        valor = match.group(0)
        if valor not in _mapa:
            _mapa[valor] = _placeholder(tipo)
        return _mapa[valor]

    texto = _RUT_PATTERN.sub(lambda m: _reemplazar(m, "RUT"), texto)
    texto = _EMAIL_PATTERN.sub(lambda m: _reemplazar(m, "EMAIL"), texto)
    texto = _DIRECCION_PATTERN.sub(lambda m: _reemplazar(m, "DIRECCION"), texto)
    return texto


# ---------------------------------------------------------------------------
# Paso 2: LLM para entidades no estructuradas (nombres, empresas)
# ---------------------------------------------------------------------------

_SYSTEM_ANON = """Eres un sistema de anonimización de datos legales chilenos.
Tu tarea es identificar y reemplazar ÚNICAMENTE entidades del tipo:
- NOMBRE: nombres propios de personas naturales
- EMPRESA: razones sociales, nombres de empresas o sociedades

Responde SOLO con un objeto JSON con dos claves:
- "nombres": lista de strings con los nombres de personas encontrados
- "empresas": lista de strings con las razones sociales encontradas

Si no hay entidades de ese tipo, devuelve una lista vacía.
No incluyas RUTs, emails ni direcciones (ya fueron procesados).
No incluyas explicaciones, solo el JSON."""


def _extraer_entidades_llm(texto: str) -> Dict[str, list]:
    """Usa el LLM para extraer nombres y empresas del texto."""
    try:
        llm = ChatOpenAI(
            model=CONFIG.llm_model,
            base_url=CONFIG.api_base_url,
            api_key=os.getenv("GITHUB_TOKEN"),
            temperature=0,
        )
        respuesta = llm.invoke([
            SystemMessage(content=_SYSTEM_ANON),
            HumanMessage(content=f"Texto a analizar:\n\n{texto[:2000]}"),
        ])
        return json.loads(respuesta.content)
    except Exception:
        # Si el LLM falla, continuar sin anonimización de nombres/empresas
        return {"nombres": [], "empresas": []}


def _anonimizar_entidades(texto: str, entidades: Dict[str, list]) -> str:
    """Reemplaza nombres y empresas identificados por el LLM."""
    for nombre in entidades.get("nombres", []):
        if nombre and nombre not in _mapa:
            _mapa[nombre] = _placeholder("NOMBRE")
        if nombre:
            texto = texto.replace(nombre, _mapa[nombre])

    for empresa in entidades.get("empresas", []):
        if empresa and empresa not in _mapa:
            _mapa[empresa] = _placeholder("EMPRESA")
        if empresa:
            texto = texto.replace(empresa, _mapa[empresa])

    return texto


# ---------------------------------------------------------------------------
# Interfaz pública
# ---------------------------------------------------------------------------

def anonimizar(texto: str) -> tuple[str, Dict[str, str]]:
    """
    Anonimiza un texto eliminando entidades sensibles.

    Args:
        texto: texto del caso a anonimizar

    Returns:
        tuple (texto_anonimizado, mapa_de_reemplazos)
        El mapa permite revertir la anonimización si es necesario.
    """
    _reset()

    # Paso 1: regex (rápido, sin API)
    texto = _anonimizar_regex(texto)

    # Paso 2: LLM (nombres y empresas)
    entidades = _extraer_entidades_llm(texto)
    texto = _anonimizar_entidades(texto, entidades)

    return texto, dict(_mapa)


def revertir(texto_anonimizado: str, mapa: Dict[str, str]) -> str:
    """
    Revierte la anonimización usando el mapa generado por anonimizar().
    Solo útil en contextos controlados (ej. mostrar el caso al abogado dueño).
    """
    mapa_invertido = {v: k for k, v in mapa.items()}
    for placeholder, original in mapa_invertido.items():
        texto_anonimizado = texto_anonimizado.replace(placeholder, original)
    return texto_anonimizado
