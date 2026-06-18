"""
test_admin.py — Tests para el sistema de monitoreo y ETL.

Uso:
    python -m pytest test_admin.py -v
"""

import os
import time
import pytest

from monitor_db import Monitor, inicializar_db, DB_PATH, DB_DIR


# ── Helpers ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def limpiar_db():
    inicializar_db()
    yield
    # Limpiar BD entre tests para aislamiento
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    for tabla in ["consultas", "logs", "metricas_diarias"]:
        conn.execute(f"DELETE FROM {tabla}")
    conn.commit()
    conn.close()


def _monitor() -> Monitor:
    """Crea un monitor limpio por test."""
    return Monitor()


# ── Tests de registro de consultas ───────────────────────────────────────

class TestRegistroConsultas:

    def test_registrar_consulta_exitosa(self):
        mon = _monitor()
        cid = mon.registrar_consulta(
            modo="EP1",
            consulta="¿Cuál es la tasa del IVA?",
            respuesta="## Análisis\nLa tasa es 19%.",
            tiene_analisis=True,
            tiene_articulos=True,
            tiene_limitaciones=True,
            num_fuentes=5,
            k_usado=8,
            temperatura=0.1,
            tiempo_ms=1234,
        )
        assert cid > 0

        c = mon.obtener_consulta(cid)
        assert c is not None
        assert c["modo"] == "EP1"
        assert c["tiene_analisis"] == 1
        assert c["tiene_articulos"] == 1
        assert c["tiene_limitaciones"] == 1
        assert c["num_fuentes"] == 5
        assert c["error"] is None

    def test_registrar_consulta_con_error(self):
        mon = _monitor()
        cid = mon.registrar_consulta(
            modo="EP2",
            consulta="consulta con error",
            error="Rate limit exceeded",
            tiempo_ms=500,
        )
        c = mon.obtener_consulta(cid)
        assert c["error"] == "Rate limit exceeded"
        assert c["tiempo_ms"] == 500

    def test_registrar_consulta_campos_parciales(self):
        mon = _monitor()
        cid = mon.registrar_consulta(
            modo="EP2",
            consulta="¿Qué es el DL 824?",
            respuesta="Solo análisis",
            tiene_analisis=True,
            iteraciones=2,
            confianza=0.85,
            tiempo_ms=2000,
        )
        c = mon.obtener_consulta(cid)
        assert c["tiene_analisis"] == 1
        assert c["tiene_articulos"] == 0
        assert c["iteraciones"] == 2
        assert c["confianza"] == 0.85

    def test_consulta_truncada_si_muy_larga(self):
        mon = _monitor()
        consulta_larga = "x" * 2000
        respuesta_larga = "y" * 10000
        cid = mon.registrar_consulta(
            modo="EP1",
            consulta=consulta_larga,
            respuesta=respuesta_larga,
            error="x" * 2000,
        )
        c = mon.obtener_consulta(cid)
        assert len(c["consulta"]) <= 1000
        assert len(c["respuesta"]) <= 5000
        assert len(c["error"]) <= 500


# ── Tests de logs ─────────────────────────────────────────────────────────

class TestLogs:

    def test_registrar_y_obtener_logs(self):
        mon = _monitor()
        mon.registrar_log("INFO", "test", "mensaje de prueba")
        mon.registrar_log("ERROR", "test", "error de prueba")
        mon.registrar_log("WARNING", "test", "warn de prueba")

        logs = mon.obtener_logs()
        assert len(logs) >= 3

    def test_filtrar_logs_por_nivel(self):
        mon = _monitor()
        mon.registrar_log("INFO", "mod1", "info msg")
        mon.registrar_log("ERROR", "mod2", "error msg")

        errors = mon.obtener_logs(nivel="ERROR")
        assert len(errors) == 1
        assert errors[0]["nivel"] == "ERROR"


# ── Tests de ETL ──────────────────────────────────────────────────────────

class TestETL:

    def test_etl_sin_datos(self):
        mon = _monitor()
        res = mon.etl_ejecutar()
        assert res["total"] == 0
        assert res["mensaje"] == "sin datos"

    def test_etl_con_consultas_exitosas(self):
        mon = _monitor()
        mon.registrar_consulta(
            modo="EP1",
            consulta="consulta 1",
            respuesta="contenido",
            tiene_analisis=True,
            tiene_articulos=True,
            tiene_limitaciones=True,
            num_fuentes=3,
            tiempo_ms=1000,
        )
        mon.registrar_consulta(
            modo="EP1",
            consulta="consulta 2",
            respuesta="contenido",
            tiene_analisis=True,
            tiene_articulos=True,
            tiene_limitaciones=False,
            num_fuentes=5,
            tiempo_ms=2000,
        )
        res = mon.etl_ejecutar()
        assert res["total"] == 2
        assert res["exitosas"] == 2
        assert res["con_error"] == 0
        # precision: (2 analisis + 2 articulos + 1 limitaciones) / (2*3) = 5/6 = 83.3
        assert res["precision_pct"] == 83.3
        # consistencia: 1 de 2 tiene las 3 secciones = 50%
        assert res["consistencia_pct"] == 50.0
        assert res["error_rate_pct"] == 0.0
        assert res["tiempo_promedio"] == 1500.0

    def test_etl_con_errores(self):
        mon = _monitor()
        mon.registrar_consulta(
            modo="EP2", consulta="ok", tiene_analisis=True,
            tiene_articulos=True, tiene_limitaciones=True, tiempo_ms=500,
        )
        mon.registrar_consulta(
            modo="EP2", consulta="fail", error="timeout", tiempo_ms=3000,
        )
        mon.registrar_consulta(
            modo="EP2", consulta="fail2", error="API error", tiempo_ms=1000,
        )
        res = mon.etl_ejecutar()
        assert res["total"] == 3
        assert res["exitosas"] == 1
        assert res["con_error"] == 2
        assert res["error_rate_pct"] == pytest.approx(66.7, rel=0.1)

    def test_etl_fecha_especifica(self):
        mon = _monitor()
        mon.registrar_consulta(modo="EP1", consulta="ayer", tiempo_ms=100)
        # fuerza timestamp manual via consulta directa
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE consultas SET timestamp = '2024-01-01T10:00:00' WHERE consulta = 'ayer'"
        )
        conn.commit()
        conn.close()

        res = mon.etl_ejecutar(fecha="2024-01-01")
        assert res["total"] == 1

        res_hoy = mon.etl_ejecutar()
        assert res_hoy["total"] == 0


# ── Tests de métricas ─────────────────────────────────────────────────────

class TestMetricas:

    def test_obtener_metricas(self):
        mon = _monitor()
        # Insertar métrica manualmente
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """INSERT INTO metricas_diarias
               (fecha, total_consultas, exitosas, con_error,
                precision_pct, consistencia_pct, error_rate_pct, tiempo_promedio)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("2024-06-01", 10, 8, 2, 80.0, 70.0, 20.0, 1500.0),
        )
        conn.execute(
            """INSERT INTO metricas_diarias
               (fecha, total_consultas, exitosas, con_error,
                precision_pct, consistencia_pct, error_rate_pct, tiempo_promedio)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("2024-06-02", 20, 18, 2, 90.0, 85.0, 10.0, 1200.0),
        )
        conn.commit()
        conn.close()

        metricas = mon.obtener_metricas(dias=30)
        assert len(metricas) >= 2

        # Orden descendente por fecha
        assert metricas[0]["fecha"] >= metricas[1]["fecha"]

    def test_obtener_resumen(self):
        mon = _monitor()
        mon.registrar_consulta(modo="EP1", consulta="test", tiempo_ms=100)
        resumen = mon.obtener_resumen()
        assert resumen["total_consultas"] >= 1
        assert resumen["ultima_consulta"] is not None


# ── Tests de consultas ───────────────────────────────────────────────────

class TestObtenerConsultas:

    def test_obtener_consultas_paginadas(self):
        mon = _monitor()
        for i in range(10):
            mon.registrar_consulta(modo="EP1", consulta=f"consulta_{i}", tiempo_ms=100)

        primeras = mon.obtener_consultas(limite=3, offset=0)
        assert len(primeras) == 3
        assert primeras[0]["consulta"] == "consulta_9"

        siguientes = mon.obtener_consultas(limite=3, offset=3)
        assert len(siguientes) == 3

    def test_obtener_consultas_por_modo(self):
        mon = _monitor()
        mon.registrar_consulta(modo="EP1", consulta="ep1_test", tiempo_ms=100)
        mon.registrar_consulta(modo="EP2", consulta="ep2_test", tiempo_ms=100)

        ep1s = mon.obtener_consultas(modo="EP1")
        assert all(c["modo"] == "EP1" for c in ep1s)

        ep2s = mon.obtener_consultas(modo="EP2")
        assert all(c["modo"] == "EP2" for c in ep2s)


# ── Tests de integración: ETL → métricas → resumen ───────────────────────

class TestIntegracion:

    def test_etl_y_metricas_flujo_completo(self):
        mon = _monitor()

        # 1. Registrar consultas de diferentes tipos
        for i in range(5):
            mon.registrar_consulta(
                modo="EP1" if i % 2 == 0 else "EP2",
                consulta=f"consulta_{i}",
                respuesta="## Análisis\nR. ## Artículos citados\nArt. 1.\n## Limitaciones\nNinguna.",
                tiene_analisis=True,
                tiene_articulos=True,
                tiene_limitaciones=True,
                num_fuentes=i + 1,
                tiempo_ms=1000 + i * 100,
            )
        mon.registrar_consulta(
            modo="EP1",
            consulta="consulta_error",
            error="API timeout",
            tiempo_ms=5000,
        )

        # 2. Ejecutar ETL
        res_etl = mon.etl_ejecutar()
        assert res_etl["total"] == 6
        assert res_etl["exitosas"] == 5
        assert res_etl["con_error"] == 1

        # 3. Obtener resumen
        resumen = mon.obtener_resumen()
        assert resumen["total_consultas"] == 6
        assert resumen["total_errores"] == 1

        # 4. Verificar métricas guardadas
        metricas = mon.obtener_metricas(dias=1)
        assert len(metricas) >= 1
        ultima = metricas[0]
        assert ultima["total_consultas"] == 6
        assert ultima["precision_pct"] > 0
        assert ultima["consistencia_pct"] > 0
        assert ultima["error_rate_pct"] > 0

    def test_logs_y_consultas_independientes(self):
        mon = _monitor()
        mon.registrar_log("INFO", "app", "App iniciada")
        mon.registrar_consulta(modo="EP1", consulta="test", tiempo_ms=100)
        mon.registrar_log("ERROR", "tools", "Error en búsqueda")

        logs = mon.obtener_logs()
        assert len(logs) >= 2

        consultas = mon.obtener_consultas()
        assert len(consultas) >= 1
