"""
test_unit.py — Tests unitarios puros (sin API ni vectorstore)

Uso:
    python -m pytest test_unit.py -v
"""

import pytest

from utils import parsear_respuesta, validar_consulta


# ── parsear_respuesta ─────────────────────────────────────────────────────────

def test_parsear_respuesta_completa():
    texto = (
        "## Análisis\nHay IVA del 19%.\n"
        "## Artículos citados\nArt. 14 DL-825.\n"
        "## Limitaciones\nNinguna."
    )
    r = parsear_respuesta(texto)
    assert r["analisis"] == "Hay IVA del 19%."
    assert r["articulos"] == "Art. 14 DL-825."
    assert r["limitaciones"] == "Ninguna."


def test_parsear_respuesta_solo_analisis():
    texto = "## Análisis\nContenido del análisis."
    r = parsear_respuesta(texto)
    assert r["analisis"] == "Contenido del análisis."
    assert r["articulos"] == ""
    assert r["limitaciones"] == ""


def test_parsear_respuesta_sin_marcadores():
    texto = "Respuesta sin estructura."
    r = parsear_respuesta(texto)
    assert r["analisis"] == "Respuesta sin estructura."
    assert r["articulos"] == ""
    assert r["limitaciones"] == ""


def test_parsear_respuesta_vacia():
    r = parsear_respuesta("")
    assert r["analisis"] == ""
    assert r["articulos"] == ""
    assert r["limitaciones"] == ""


def test_parsear_respuesta_multilinea():
    texto = (
        "## Análisis\n"
        "Línea 1.\n"
        "Línea 2.\n"
        "## Artículos citados\n"
        "- Art. 1\n"
        "- Art. 2\n"
        "## Limitaciones\n"
        "No hay información sobre tasas especiales."
    )
    r = parsear_respuesta(texto)
    assert "Línea 1." in r["analisis"]
    assert "Línea 2." in r["analisis"]
    assert "Art. 1" in r["articulos"]
    assert "Art. 2" in r["articulos"]
    assert "tasas especiales" in r["limitaciones"]


def test_parsear_respuesta_espacios_extra():
    texto = "  ## Análisis  \nContenido.\n  ## Artículos citados  \nArt. 5.\n  ## Limitaciones  \nNinguna."
    r = parsear_respuesta(texto)
    # Los marcadores con espacios NO deben reconocerse (strip solo se aplica al comparar)
    # El texto completo cae en el fallback de analisis
    assert r["analisis"] != ""


# ── validar_consulta ──────────────────────────────────────────────────────────

def test_validar_consulta_normal():
    assert validar_consulta("¿Cuál es la tasa del IVA?") == "¿Cuál es la tasa del IVA?"


def test_validar_consulta_strip():
    assert validar_consulta("  consulta con espacios  ") == "consulta con espacios"


def test_validar_consulta_vacia():
    with pytest.raises(ValueError, match="vacía"):
        validar_consulta("")


def test_validar_consulta_solo_espacios():
    with pytest.raises(ValueError, match="vacía"):
        validar_consulta("   ")


def test_validar_consulta_muy_larga():
    texto_largo = "a" * 501
    with pytest.raises(ValueError, match="500 caracteres"):
        validar_consulta(texto_largo)


def test_validar_consulta_limite_exacto():
    texto_limite = "a" * 500
    assert validar_consulta(texto_limite) == texto_limite
