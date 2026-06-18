"""
test_anonymizer.py — Tests para el pipeline de anonimización.

Uso:
    python -m pytest test_anonymizer.py -v
"""

import re
from unittest.mock import patch

import pytest

from anonymizer import (
    _anonimizar_entidades,
    _anonimizar_regex,
    _EMAIL_PATTERN,
    _extraer_entidades_llm,
    _placeholder,
    _reset,
    _RUT_PATTERN,
    _DIRECCION_PATTERN,
    anonimizar,
    revertir,
)


# ── Helpers ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_contadores():
    """Cada test empieza con contadores y mapa limpios."""
    _reset()
    yield


# ── Tests de patrones regex ───────────────────────────────────────────────

class TestPatronesRegex:

    @pytest.mark.parametrize("rut", [
        "12.345.678-9",
        "1.234.567-K",
        "1.234.567-k",
        "12345678-9",
        "7.891.011-2",
        "23.456.789-0",
    ])
    def test_rut_valido(self, rut):
        assert _RUT_PATTERN.search(rut), f"RUT {rut!r} no fue detectado"

    @pytest.mark.parametrize("no_rut", [
        "12345",
        "12.345.678",
        "RUT 12.345.678-",
        "solo texto",
        "",
        "12.345.678-90",  # 2 dígitos verificadores
    ])
    def test_no_rut(self, no_rut):
        assert not _RUT_PATTERN.search(no_rut), f"Falso positivo: {no_rut!r}"

    @pytest.mark.parametrize("email", [
        "juan@perez.cl",
        "j.perez@dominio-largo.com",
        "a+b@test.dev",
        "user@sub.domain.co",
    ])
    def test_email_valido(self, email):
        assert _EMAIL_PATTERN.search(email), f"Email {email!r} no fue detectado"

    @pytest.mark.parametrize("no_email", [
        "juan@perez",
        "@dominio.com",
        "sin arroba",
        "",
    ])
    def test_no_email(self, no_email):
        assert not _EMAIL_PATTERN.search(no_email), f"Falso positivo: {no_email!r}"

    @pytest.mark.parametrize("direccion", [
        "Av. Providencia 1234",
        "Calle Huérfanos 567",
        "Avenida Libertador 1000",
        "Pasaje Los Olivos 890",
        "Camino El Alba 4567",
    ])
    def test_direccion_valida(self, direccion):
        assert _DIRECCION_PATTERN.search(direccion), f"Dirección {direccion!r} no fue detectada"

    @pytest.mark.parametrize("no_direccion", [
        "Santiago",
        "Calle 123",  # nombre de calle muy corto
        "Av. 1234",   # falta nombre de calle
        "",
    ])
    def test_no_direccion(self, no_direccion):
        assert not _DIRECCION_PATTERN.search(no_direccion), f"Falso positivo: {no_direccion!r}"


# ── Tests de placeholder ──────────────────────────────────────────────────

class TestPlaceholder:

    def test_placeholder_secuencial(self):
        assert _placeholder("RUT") == "[RUT_1]"
        assert _placeholder("RUT") == "[RUT_2]"
        assert _placeholder("NOMBRE") == "[NOMBRE_1]"

    def test_placeholder_independiente_por_tipo(self):
        assert _placeholder("RUT") == "[RUT_1]"
        assert _placeholder("EMAIL") == "[EMAIL_1]"
        assert _placeholder("RUT") == "[RUT_2]"

    def test_reset_reinicia_contadores(self):
        _placeholder("RUT")
        _placeholder("RUT")
        assert _placeholder("RUT") == "[RUT_3]"
        _reset()
        assert _placeholder("RUT") == "[RUT_1]"


# ── Tests de anonimización regex ──────────────────────────────────────────

class TestAnonimizarRegex:

    def test_reemplaza_rut(self):
        result = _anonimizar_regex("El RUT del cliente es 12.345.678-9")
        assert "[RUT_1]" in result
        assert "12.345.678-9" not in result

    def test_reemplaza_email(self):
        result = _anonimizar_regex("Contacto: juan@perez.cl")
        assert "[EMAIL_1]" in result
        assert "juan@perez.cl" not in result

    def test_reemplaza_direccion(self):
        result = _anonimizar_regex("Dirección: Av. Providencia 1234")
        assert "[DIRECCION_1]" in result
        assert "Av. Providencia 1234" not in result

    def test_reemplaza_multiple(self):
        result = _anonimizar_regex(
            "RUT 12.345.678-9 y RUT 98.765.432-1, email juan@perez.cl"
        )
        assert "[RUT_1]" in result
        assert "[RUT_2]" in result
        assert "[EMAIL_1]" in result
        assert "12.345.678-9" not in result
        assert "98.765.432-1" not in result

    def test_reutiliza_placeholder_mismo_valor(self):
        result = _anonimizar_regex("RUT 12.345.678-9 y también RUT 12.345.678-9")
        assert result.count("[RUT_1]") == 2
        assert "[RUT_2]" not in result

    def test_texto_sin_entidades(self):
        result = _anonimizar_regex("¿Cuál es la tasa del IVA?")
        assert result == "¿Cuál es la tasa del IVA?"

    def test_texto_vacio(self):
        assert _anonimizar_regex("") == ""


# ── Tests de anonimización de entidades LLM ───────────────────────────────

class TestAnonimizarEntidades:

    def test_reemplaza_nombres(self):
        _reset()
        entidades = {"nombres": ["Juan Pérez"], "empresas": []}
        result = _anonimizar_entidades("El cliente Juan Pérez solicitó", entidades)
        assert "[NOMBRE_1]" in result
        assert "Juan Pérez" not in result

    def test_reemplaza_empresas(self):
        _reset()
        entidades = {"nombres": [], "empresas": ["Ruiz Salazar Tributaria"]}
        result = _anonimizar_entidades("La empresa Ruiz Salazar Tributaria", entidades)
        assert "[EMPRESA_1]" in result
        assert "Ruiz Salazar Tributaria" not in result

    def test_nombre_y_empresa(self):
        _reset()
        entidades = {
            "nombres": ["María González"],
            "empresas": ["Auditores Asociados Ltda."],
        }
        result = _anonimizar_entidades(
            "María González de Auditores Asociados Ltda.", entidades
        )
        assert "[NOMBRE_1]" in result
        assert "[EMPRESA_1]" in result
        assert "María González" not in result
        assert "Auditores Asociados Ltda." not in result

    def test_entidades_vacias(self):
        _reset()
        entidades = {"nombres": [], "empresas": []}
        result = _anonimizar_entidades("Texto sin entidades", entidades)
        assert result == "Texto sin entidades"


# ── Tests del pipeline completo ───────────────────────────────────────────

class TestPipelineCompleto:

    @patch("anonymizer._extraer_entidades_llm")
    def test_anonimizar_pipeline(self, mock_llm):
        mock_llm.return_value = {
            "nombres": ["Juan Pérez"],
            "empresas": ["Ruiz Salazar"],
        }
        texto = (
            "El cliente Juan Pérez, RUT 12.345.678-9, "
            "de la empresa Ruiz Salazar, ubicada en Av. Providencia 1234, "
            "email juan@perez.cl"
        )
        anon, mapa = anonimizar(texto)

        assert "Juan Pérez" not in anon
        assert "12.345.678-9" not in anon
        assert "Ruiz Salazar" not in anon
        assert "Av. Providencia 1234" not in anon
        assert "juan@perez.cl" not in anon

        assert "[RUT_1]" in anon
        assert "[NOMBRE_1]" in anon
        assert "[EMPRESA_1]" in anon
        assert "[DIRECCION_1]" in anon
        assert "[EMAIL_1]" in anon

        # Verificar mapa de reemplazos
        assert len(mapa) == 5

    @patch("anonymizer._extraer_entidades_llm")
    def test_revertir(self, mock_llm):
        mock_llm.return_value = {
            "nombres": ["Juan Pérez"],
            "empresas": ["Ruiz Salazar"],
        }
        texto = "Juan Pérez, RUT 12.345.678-9, Ruiz Salazar"
        anon, mapa = anonimizar(texto)
        restaurado = revertir(anon, mapa)
        assert restaurado == texto

    @patch("anonymizer._extraer_entidades_llm")
    def test_mapa_reemplazos_completo(self, mock_llm):
        mock_llm.return_value = {
            "nombres": ["Ana López"],
            "empresas": ["Bufete ABC"],
        }
        _, mapa = anonimizar("Ana López, RUT 1.234.567-K, email ana@bufete.cl")
        # El mapa debe tener entradas original -> placeholder
        assert "Ana López" in mapa
        assert "1.234.567-K" in mapa
        assert "ana@bufete.cl" in mapa
        assert "Bufete ABC" in mapa
        # Verificar formato de placeholders
        for v in mapa.values():
            assert re.match(r"^\[\w+_\d+\]$", v)

    @patch("anonymizer._extraer_entidades_llm")
    def test_sin_entidades(self, mock_llm):
        mock_llm.return_value = {"nombres": [], "empresas": []}
        texto = "¿Cuál es la tasa del IVA en Chile?"
        anon, mapa = anonimizar(texto)
        assert anon == texto
        assert mapa == {}

    def test_extraer_entidades_llm_fallback(self):
        """Sin API key debe lanzar excepción capturada y retornar vacío."""
        result = _extraer_entidades_llm("Texto de prueba")
        # Verificar que el fallback sea listas vacías
        assert result == {"nombres": [], "empresas": []}


# ── Tests de integración con datos reales ─────────────────────────────────

class TestIntegracion:

    @patch("anonymizer._extraer_entidades_llm")
    def test_caso_legal_tipico(self, mock_llm):
        mock_llm.return_value = {
            "nombres": ["Martín Higuera"],
            "empresas": ["Ruiz Salazar Tributaria"],
        }
        texto = (
            "RESUMEN DEL CASO:\n"
            "Cliente: Martín Higuera\n"
            "RUT: 15.123.456-7\n"
            "Dirección: Av. Apoquindo 3000, Santiago\n"
            "Email: mhiguera@example.com\n"
            "Empresa: Ruiz Salazar Tributaria\n\n"
            "Consulta sobre aplicación de IVA en servicios de consultoría."
        )
        anon, mapa = anonimizar(texto)

        assert "Martín Higuera" not in anon
        assert "15.123.456-7" not in anon
        assert "Av. Apoquindo 3000" not in anon
        assert "mhiguera@example.com" not in anon
        assert "Ruiz Salazar Tributaria" not in anon

        assert "[NOMBRE_1]" in anon
        assert "[RUT_1]" in anon
        assert "[DIRECCION_1]" in anon
        assert "[EMAIL_1]" in anon
        assert "[EMPRESA_1]" in anon

        consulta_lower = anon.lower()
        assert "consulta" in consulta_lower
        assert "iva" in consulta_lower
        assert "servicios" in consulta_lower

        assert revertir(anon, mapa) == texto
