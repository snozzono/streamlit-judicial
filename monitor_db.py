"""
monitor_db.py — SQLite-backed monitoring and ETL pipeline.

Tracks precision, consistency, and error frequency across all
consultations. Provides an ETL pipeline that extracts data from
the running program, transforms it into metrics, and loads it
into local SQLite tables.

Usage:
    from monitor_db import Monitor

    monitor = Monitor()
    monitor.registrar_consulta(...)
    monitor.etl_ejecutar()
"""

import json
import logging
import os
import sqlite3
import statistics
import time
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(_BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "monitor.db")


# ═══════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════

def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hoy() -> str:
    return date.today().isoformat()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    den = sum((x - mean_x) ** 2 for x in xs)
    return num / den if den else 0.0


# ═══════════════════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS consultas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    modo            TEXT    NOT NULL,
    consulta        TEXT    NOT NULL,
    respuesta       TEXT,
    tiene_analisis  INTEGER DEFAULT 0,
    tiene_articulos INTEGER DEFAULT 0,
    tiene_limitaciones INTEGER DEFAULT 0,
    num_fuentes     INTEGER DEFAULT 0,
    k_usado         INTEGER,
    temperatura     REAL,
    iteraciones     INTEGER DEFAULT 0,
    confianza       REAL,
    error           TEXT,
    tiempo_ms       REAL,
    tokens_input    INTEGER DEFAULT 0,
    tokens_output   INTEGER DEFAULT 0,
    tokens_total    INTEGER DEFAULT 0,
    costo_estimado  REAL    DEFAULT 0,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT    NOT NULL,
    nivel      TEXT    NOT NULL,
    modulo     TEXT,
    mensaje    TEXT    NOT NULL,
    created_at TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS metricas_diarias (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha            TEXT    NOT NULL UNIQUE,
    total_consultas  INTEGER DEFAULT 0,
    exitosas         INTEGER DEFAULT 0,
    con_error        INTEGER DEFAULT 0,
    precision_pct    REAL    DEFAULT 0,
    consistencia_pct REAL    DEFAULT 0,
    error_rate_pct   REAL    DEFAULT 0,
    tiempo_promedio  REAL    DEFAULT 0,
    tokens_input_total    INTEGER DEFAULT 0,
    tokens_output_total   INTEGER DEFAULT 0,
    tokens_total          INTEGER DEFAULT 0,
    avg_tokens_por_consulta REAL DEFAULT 0,
    avg_costo_por_consulta  REAL DEFAULT 0,
    created_at       TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_consultas_timestamp ON consultas(timestamp);
CREATE INDEX IF NOT EXISTS idx_consultas_modo ON consultas(modo);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_nivel ON logs(nivel);
"""


def inicializar_db():
    conn = _get_conn()
    conn.executescript(SCHEMA_SQL)
    for table, col, col_type in [
        ("consultas", "tokens_input", "INTEGER DEFAULT 0"),
        ("consultas", "tokens_output", "INTEGER DEFAULT 0"),
        ("consultas", "tokens_total", "INTEGER DEFAULT 0"),
        ("consultas", "costo_estimado", "REAL DEFAULT 0"),
        ("metricas_diarias", "tokens_input_total", "INTEGER DEFAULT 0"),
        ("metricas_diarias", "tokens_output_total", "INTEGER DEFAULT 0"),
        ("metricas_diarias", "tokens_total", "INTEGER DEFAULT 0"),
        ("metricas_diarias", "avg_tokens_por_consulta", "REAL DEFAULT 0"),
        ("metricas_diarias", "avg_costo_por_consulta", "REAL DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Monitor class
# ═══════════════════════════════════════════════════════════════════════

class Monitor:
    """Single source of truth for app monitoring and metrics."""

    def __init__(self):
        inicializar_db()

    # ── Consultas ────────────────────────────────────────────────────────

    def registrar_consulta(
        self,
        *,
        modo: str,
        consulta: str,
        respuesta: str = "",
        tiene_analisis: bool = False,
        tiene_articulos: bool = False,
        tiene_limitaciones: bool = False,
        num_fuentes: int = 0,
        k_usado: Optional[int] = None,
        temperatura: Optional[float] = None,
        iteraciones: int = 0,
        confianza: Optional[float] = None,
        error: Optional[str] = None,
        tiempo_ms: float = 0,
        tokens_input: int = 0,
        tokens_output: int = 0,
        costo_estimado: float = 0.0,
    ) -> int:
        tokens_total = tokens_input + tokens_output
        conn = _get_conn()
        try:
            cur = conn.execute(
                """INSERT INTO consultas
                   (timestamp, modo, consulta, respuesta,
                    tiene_analisis, tiene_articulos, tiene_limitaciones,
                    num_fuentes, k_usado, temperatura, iteraciones,
                    confianza, error, tiempo_ms,
                    tokens_input, tokens_output, tokens_total, costo_estimado)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _ahora(),
                    modo,
                    consulta[:1000],
                    respuesta[:5000] if respuesta else "",
                    int(tiene_analisis),
                    int(tiene_articulos),
                    int(tiene_limitaciones),
                    num_fuentes,
                    k_usado,
                    temperatura,
                    iteraciones,
                    confianza,
                    error[:500] if error else None,
                    tiempo_ms,
                    tokens_input,
                    tokens_output,
                    tokens_total,
                    costo_estimado,
                ),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    # ── Logs ─────────────────────────────────────────────────────────────

    def registrar_log(self, nivel: str, modulo: str, mensaje: str):
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO logs (timestamp, nivel, modulo, mensaje) VALUES (?, ?, ?, ?)",
                (_ahora(), nivel.upper(), modulo[:100], mensaje[:2000]),
            )
            conn.commit()
        finally:
            conn.close()

    # ── ETL: extraer → transformar → cargar métricas diarias ────────────

    def etl_ejecutar(self, fecha: Optional[str] = None) -> dict:
        fecha = fecha or _hoy()
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM consultas WHERE date(timestamp) = ?", (fecha,)
            ).fetchall()

            total = len(rows)
            if total == 0:
                return {"fecha": fecha, "total": 0, "mensaje": "sin datos"}

            exitosas = sum(1 for r in rows if r["error"] is None)
            con_error = total - exitosas

            analisis_ok = sum(1 for r in rows if r["tiene_analisis"])
            articulos_ok = sum(1 for r in rows if r["tiene_articulos"])
            limitaciones_ok = sum(1 for r in rows if r["tiene_limitaciones"])

            precision_pct = round(
                (analisis_ok + articulos_ok + limitaciones_ok) / (total * 3) * 100, 1
            ) if total else 0.0

            consistencia_pct = round(
                sum(
                    1
                    for r in rows
                    if r["tiene_analisis"]
                    and r["tiene_articulos"]
                    and r["tiene_limitaciones"]
                )
                / total
                * 100,
                1,
            ) if total else 0.0

            error_rate_pct = round(con_error / total * 100, 1) if total else 0.0

            tiempos = [r["tiempo_ms"] for r in rows if r["tiempo_ms"] is not None]
            tiempo_promedio = round(sum(tiempos) / len(tiempos), 1) if tiempos else 0.0

            tokens_input_total = sum(r["tokens_input"] or 0 for r in rows)
            tokens_output_total = sum(r["tokens_output"] or 0 for r in rows)
            tokens_total = tokens_input_total + tokens_output_total
            avg_tokens_por_consulta = round(tokens_total / total, 1) if total else 0.0
            costos = [r["costo_estimado"] or 0 for r in rows]
            avg_costo_por_consulta = round(sum(costos) / total, 4) if total else 0.0

            conn.execute(
                """INSERT INTO metricas_diarias
                   (fecha, total_consultas, exitosas, con_error,
                    precision_pct, consistencia_pct, error_rate_pct, tiempo_promedio,
                    tokens_input_total, tokens_output_total, tokens_total,
                    avg_tokens_por_consulta, avg_costo_por_consulta)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(fecha) DO UPDATE SET
                       total_consultas  = excluded.total_consultas,
                       exitosas         = excluded.exitosas,
                       con_error        = excluded.con_error,
                       precision_pct    = excluded.precision_pct,
                       consistencia_pct = excluded.consistencia_pct,
                       error_rate_pct   = excluded.error_rate_pct,
                       tiempo_promedio  = excluded.tiempo_promedio,
                       tokens_input_total    = excluded.tokens_input_total,
                       tokens_output_total   = excluded.tokens_output_total,
                       tokens_total          = excluded.tokens_total,
                       avg_tokens_por_consulta = excluded.avg_tokens_por_consulta,
                       avg_costo_por_consulta  = excluded.avg_costo_por_consulta""",
                (
                    fecha,
                    total,
                    exitosas,
                    con_error,
                    precision_pct,
                    consistencia_pct,
                    error_rate_pct,
                    tiempo_promedio,
                    tokens_input_total,
                    tokens_output_total,
                    tokens_total,
                    avg_tokens_por_consulta,
                    avg_costo_por_consulta,
                ),
            )
            conn.commit()

            return {
                "fecha": fecha,
                "total": total,
                "exitosas": exitosas,
                "con_error": con_error,
                "precision_pct": precision_pct,
                "consistencia_pct": consistencia_pct,
                "error_rate_pct": error_rate_pct,
                "tiempo_promedio": tiempo_promedio,
                "tokens_input_total": tokens_input_total,
                "tokens_output_total": tokens_output_total,
                "tokens_total": tokens_total,
                "avg_tokens_por_consulta": avg_tokens_por_consulta,
                "avg_costo_por_consulta": avg_costo_por_consulta,
            }
        finally:
            conn.close()

    # ── Consultas ────────────────────────────────────────────────────────

    def obtener_consultas(
        self,
        limite: int = 100,
        offset: int = 0,
        modo: Optional[str] = None,
    ) -> list[dict]:
        conn = _get_conn()
        try:
            if modo:
                rows = conn.execute(
                    "SELECT * FROM consultas WHERE modo = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (modo, limite, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM consultas ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limite, offset),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def obtener_consulta(self, consulta_id: int) -> Optional[dict]:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM consultas WHERE id = ?", (consulta_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ── Logs ─────────────────────────────────────────────────────────────

    def obtener_logs(
        self, limite: int = 100, nivel: Optional[str] = None
    ) -> list[dict]:
        conn = _get_conn()
        try:
            if nivel:
                rows = conn.execute(
                    "SELECT * FROM logs WHERE nivel = ? ORDER BY id DESC LIMIT ?",
                    (nivel.upper(), limite),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limite,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Métricas ─────────────────────────────────────────────────────────

    def obtener_metricas(
        self, dias: int = 30
    ) -> list[dict]:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM metricas_diarias ORDER BY fecha DESC LIMIT ?",
                (dias,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def obtener_resumen(self) -> dict:
        conn = _get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM consultas").fetchone()[0]
            errores = conn.execute(
                "SELECT COUNT(*) FROM consultas WHERE error IS NOT NULL"
            ).fetchone()[0]
            ultima_consulta = conn.execute(
                "SELECT timestamp FROM consultas ORDER BY id DESC LIMIT 1"
            ).fetchone()
            ultima_metricas = conn.execute(
                "SELECT * FROM metricas_diarias ORDER BY fecha DESC LIMIT 1"
            ).fetchone()
            return {
                "total_consultas": total,
                "total_errores": errores,
                "tasa_error_pct": round(errores / total * 100, 1) if total else 0.0,
                "ultima_consulta": dict(ultima_consulta)["timestamp"]
                if ultima_consulta
                else None,
                "ultimas_metricas": dict(ultima_metricas) if ultima_metricas else None,
            }
        finally:
            conn.close()

    # ── Anomaly Detection ────────────────────────────────────────────────

    def detectar_anomalias(self, dias: int = 7) -> dict:
        conn = _get_conn()
        try:
            metricas = conn.execute(
                "SELECT * FROM metricas_diarias ORDER BY fecha DESC LIMIT ?",
                (dias,),
            ).fetchall()

            if not metricas:
                return {
                    "picos_error": [],
                    "picos_latencia": [],
                    "tendencia_precision": "estable",
                    "patrones_fallo": {},
                }

            rates = [m["error_rate_pct"] for m in metricas if m["error_rate_pct"] is not None]
            mean_rate = statistics.mean(rates) if rates else 0
            std_rate = statistics.stdev(rates) if len(rates) > 1 else 0
            threshold_error = mean_rate + 2 * std_rate

            fecha_inicio = metricas[-1]["fecha"]
            picos_error = [
                {
                    "fecha": m["fecha"],
                    "error_rate_pct": m["error_rate_pct"],
                    "threshold": round(threshold_error, 1),
                }
                for m in metricas
                if m["error_rate_pct"] is not None and m["error_rate_pct"] > threshold_error
            ]

            consultas = conn.execute(
                "SELECT * FROM consultas WHERE date(timestamp) >= ? AND tiempo_ms IS NOT NULL",
                (fecha_inicio,),
            ).fetchall()

            if consultas:
                latencias = [c["tiempo_ms"] for c in consultas if c["tiempo_ms"] is not None]
                mean_lat = statistics.mean(latencias) if latencias else 0
                std_lat = statistics.stdev(latencias) if len(latencias) > 1 else 0
                threshold_lat = mean_lat + 3 * std_lat
                outliers = [
                    dict(c)
                    for c in consultas
                    if c["tiempo_ms"] is not None and c["tiempo_ms"] > threshold_lat
                ]
                outliers.sort(key=lambda x: x["tiempo_ms"], reverse=True)
                picos_latencia = outliers[:10]
            else:
                picos_latencia = []

            valores_precision = [
                m["precision_pct"]
                for m in metricas
                if m["precision_pct"] is not None
            ]
            valores_precision.reverse()
            slope_precision = _slope(valores_precision) if len(valores_precision) >= 2 else 0

            if slope_precision > 0.5:
                tendencia_precision = "mejorando"
            elif slope_precision < -0.5:
                tendencia_precision = "empeorando"
            else:
                tendencia_precision = "estable"

            errores = conn.execute(
                """SELECT error, COUNT(*) as cnt
                   FROM consultas
                   WHERE date(timestamp) >= ? AND error IS NOT NULL
                   GROUP BY error
                   ORDER BY cnt DESC""",
                (fecha_inicio,),
            ).fetchall()
            patrones_fallo = {r["error"]: r["cnt"] for r in errores}

            return {
                "picos_error": picos_error,
                "picos_latencia": picos_latencia,
                "tendencia_precision": tendencia_precision,
                "patrones_fallo": patrones_fallo,
            }
        finally:
            conn.close()

    def recomendar_optimizaciones(self) -> list[dict]:
        conn = _get_conn()
        try:
            metricas = conn.execute(
                "SELECT * FROM metricas_diarias ORDER BY fecha DESC LIMIT 7"
            ).fetchall()
            recomendaciones = []

            if metricas:
                rates = [m["error_rate_pct"] for m in metricas if m["error_rate_pct"] is not None]
                if rates:
                    avg_error = sum(rates) / len(rates)
                    if avg_error > 10:
                        recomendaciones.append({
                            "area": "errores",
                            "problema": f"Tasa de error promedio alta: {avg_error:.1f}%",
                            "recomendacion": "Revisar manejo de excepciones y validar entradas del modelo",
                            "impacto_esperado": "Reducir tasa de error por debajo del 5%",
                            "prioridad": "alta",
                        })

                tiempos = [m["tiempo_promedio"] for m in metricas if m["tiempo_promedio"] is not None]
                if tiempos:
                    avg_tiempo = sum(tiempos) / len(tiempos)
                    if avg_tiempo > 5000:
                        recomendaciones.append({
                            "area": "latencia",
                            "problema": f"Tiempo promedio de respuesta alto: {avg_tiempo:.0f}ms",
                            "recomendacion": "Optimizar consultas, reducir k_usado o usar un modelo más rápido",
                            "impacto_esperado": "Reducir latencia promedio por debajo de 2s",
                            "prioridad": "alta",
                        })

                tokens = [m["avg_tokens_por_consulta"] for m in metricas if m["avg_tokens_por_consulta"] is not None]
                if tokens:
                    avg_tokens = sum(tokens) / len(tokens)
                    if avg_tokens > 2000:
                        recomendaciones.append({
                            "area": "tokens",
                            "problema": f"Consumo promedio alto de tokens: {avg_tokens:.0f} por consulta",
                            "recomendacion": "Acortar consultas, reducir contexto o implementar resumen previo",
                            "impacto_esperado": "Reducir costo estimado en tokens",
                            "prioridad": "media",
                        })

                costos = [m["avg_costo_por_consulta"] for m in metricas if m["avg_costo_por_consulta"] is not None]
                if costos:
                    avg_costo = sum(costos) / len(costos)
                    if avg_costo > 0.05:
                        recomendaciones.append({
                            "area": "costo",
                            "problema": f"Costo promedio elevado: ${avg_costo:.4f} por consulta",
                            "recomendacion": "Revisar uso de modelo, reducir temperatura o implementar cache",
                            "impacto_esperado": "Reducir costo operativo",
                            "prioridad": "media",
                        })

                precisiones = [m["precision_pct"] for m in metricas if m["precision_pct"] is not None]
                if precisiones and len(precisiones) >= 2:
                    precisiones_rev = list(reversed(precisiones))
                    slope_p = _slope(precisiones_rev)
                    if slope_p < -1:
                        recomendaciones.append({
                            "area": "precision",
                            "problema": "Precisión en declive",
                            "recomendacion": "Revisar calidad de fuentes y umbrales de análisis",
                            "impacto_esperado": "Detener caída y recuperar precisión",
                            "prioridad": "alta",
                        })

            if not recomendaciones:
                recomendaciones.append({
                    "area": "general",
                    "problema": "Sin anomalías detectadas",
                    "recomendacion": "Monitoreo nominal, continuar con operativa actual",
                    "impacto_esperado": "Mantener calidad del servicio",
                    "prioridad": "baja",
                })

            return recomendaciones
        finally:
            conn.close()

    # ── Trend Analysis ───────────────────────────────────────────────────

    def obtener_tendencia_metricas(self, dias: int = 30) -> dict:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM metricas_diarias ORDER BY fecha ASC LIMIT ?",
                (dias,),
            ).fetchall()

            precision_vals = [r["precision_pct"] for r in rows if r["precision_pct"] is not None]
            consistencia_vals = [r["consistencia_pct"] for r in rows if r["consistencia_pct"] is not None]
            error_rate_vals = [r["error_rate_pct"] for r in rows if r["error_rate_pct"] is not None]
            latency_vals = [r["tiempo_promedio"] for r in rows if r["tiempo_promedio"] is not None]
            tokens_vals = [r["avg_tokens_por_consulta"] for r in rows if r["avg_tokens_por_consulta"] is not None]

            fechas = [r["fecha"] for r in rows]

            def build_series(fechas_list, values):
                return [
                    {"fecha": f, "valor": v}
                    for f, v in zip(fechas_list, values)
                ]

            return {
                "precision": {
                    "serie": build_series(fechas, precision_vals),
                    "slope": round(_slope(precision_vals), 4) if len(precision_vals) >= 2 else 0,
                },
                "consistencia": {
                    "serie": build_series(fechas, consistencia_vals),
                    "slope": round(_slope(consistencia_vals), 4) if len(consistencia_vals) >= 2 else 0,
                },
                "error_rate": {
                    "serie": build_series(fechas, error_rate_vals),
                    "slope": round(_slope(error_rate_vals), 4) if len(error_rate_vals) >= 2 else 0,
                },
                "latencia": {
                    "serie": build_series(fechas, latency_vals),
                    "slope": round(_slope(latency_vals), 4) if len(latency_vals) >= 2 else 0,
                },
                "tokens": {
                    "serie": build_series(fechas, tokens_vals),
                    "slope": round(_slope(tokens_vals), 4) if len(tokens_vals) >= 2 else 0,
                },
                "dias_analizados": len(rows),
                "fecha_inicio": fechas[0] if fechas else None,
                "fecha_fin": fechas[-1] if fechas else None,
            }
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════════════

_monitor_instance: Optional[Monitor] = None


def get_monitor() -> Monitor:
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = Monitor()
    return _monitor_instance
