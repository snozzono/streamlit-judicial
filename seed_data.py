"""Seed test data into monitor.db for dashboard testing."""
import sqlite3
import os
from datetime import datetime, timedelta
from random import randint, choice, uniform

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(_BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "monitor.db")
os.makedirs(DB_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.executescript("""
    CREATE TABLE IF NOT EXISTS consultas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        modo TEXT NOT NULL,
        consulta TEXT NOT NULL,
        respuesta TEXT,
        tiene_analisis INTEGER DEFAULT 0,
        tiene_articulos INTEGER DEFAULT 0,
        tiene_limitaciones INTEGER DEFAULT 0,
        num_fuentes INTEGER DEFAULT 0,
        k_usado INTEGER,
        temperatura REAL,
        iteraciones INTEGER DEFAULT 0,
        confianza REAL,
        error TEXT,
        tiempo_ms REAL,
        tokens_input INTEGER DEFAULT 500,
        tokens_output INTEGER DEFAULT 200,
        costo_estimado REAL DEFAULT 0.001,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        nivel TEXT NOT NULL,
        modulo TEXT,
        mensaje TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS metricas_diarias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL UNIQUE,
        total_consultas INTEGER DEFAULT 0,
        exitosas INTEGER DEFAULT 0,
        con_error INTEGER DEFAULT 0,
        precision_pct REAL DEFAULT 0,
        consistencia_pct REAL DEFAULT 0,
        error_rate_pct REAL DEFAULT 0,
        tiempo_promedio REAL DEFAULT 0,
        tokens_input_total INTEGER DEFAULT 0,
        tokens_output_total INTEGER DEFAULT 0,
        tokens_total INTEGER DEFAULT 0,
        avg_tokens_por_consulta REAL DEFAULT 0,
        avg_costo_por_consulta REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
""")
for table, col, col_type in [
    ("consultas", "tokens_input", "INTEGER DEFAULT 0"),
    ("consultas", "tokens_output", "INTEGER DEFAULT 0"),
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

conn.executescript("DELETE FROM consultas; DELETE FROM logs; DELETE FROM metricas_diarias")

today = datetime.now()
consultas_ejemplo = [
    "¿Cuál es la tasa del IVA en Chile?",
    "¿Qué es el DL 824?",
    "¿Cómo calculo el impuesto de primera categoría?",
    "¿Cuándo vence el plazo para declarar renta?",
    "¿Qué gastos son deducibles de impuestos?",
    "¿Cómo tributan las empresas del artículo 14?",
    "¿Cuánto es el monto maximo del FUT?",
    "¿Que es el impuesto unico de segunda categoria?",
    "¿Como se calcula el credito por capacitacion?",
    "¿Las pymes tienen beneficios tributarios?",
    "¿Como funciona el IVA en servicios digitales?",
    "¿Que es la renta presunta?",
    "¿Como tributan las sociedades de inversion?",
    "¿Cuando debo emitir boleta electronica?",
]

# ── Daily profiles: (total_q, exitosas, avg_latency_ms, precision_pct) ──
# Day -6 to today (7 days). Day index 0 = oldest, 6 = today
profiles = [
    (15, 14, 800,  85),   # 0:  Normal day, ~7% error
    (18, 16, 750,  82),   # 1:  Normal day, ~11% error
    (12, 11, 900,  88),   # 2:  Normal day, ~8% error
    (14,  4, 1100, 55),   # 3:  ERROR SPIKE ~71% error
    (20, 18, 850,  79),   # 4:  Normal day, ~10% error
    (16, 15, 950,  76),   # 5:  Normal day, ~6% error
    (10,  8, 3500, 62),   # 6:  TODAY - high latency, moderate precision
]

for day_idx, (total_q, exitosas, avg_lat, prec) in enumerate(profiles):
    day_date = today - timedelta(days=6 - day_idx)
    error_count = total_q - exitosas

    for q_idx in range(total_q):
        ts = day_date.replace(
            hour=randint(8, 20), minute=randint(0, 59), second=randint(0, 59)
        ).isoformat(timespec="seconds")

        is_error = q_idx >= exitosas
        tiene_a = 1
        tiene_art = 1 if not is_error else 0
        tiene_l = 1

        # Latency profile: most normal, some outliers on day 6
        if day_idx == 6 and q_idx in [0, 1, 2]:
            lat = randint(12000, 22000)
        elif day_idx == 6 and q_idx in [3, 4]:
            lat = randint(6000, 9000)
        else:
            lat = randint(int(avg_lat * 0.6), int(avg_lat * 1.4))

        # Error messages concentrated on spike day
        if is_error:
            if day_idx == 3:
                err_type = ["API timeout", "API timeout", "Rate limit exceeded",
                            "API timeout", "Embedding error", "Rate limit exceeded",
                            "Context length exceeded", "API timeout",
                            "Rate limit exceeded", "API timeout"][q_idx - exitosas]
            else:
                err_type = choice(["Rate limit exceeded", "API timeout", "Embedding error"])
        else:
            err_type = None

        modo = "EP1" if q_idx % 2 == 0 else "EP2"
        consulta = consultas_ejemplo[q_idx % len(consultas_ejemplo)]

        conn.execute(
            """INSERT INTO consultas
               (timestamp, modo, consulta, respuesta,
                tiene_analisis, tiene_articulos, tiene_limitaciones,
                num_fuentes, k_usado, temperatura, iteraciones,
                confianza, error, tiempo_ms,
                tokens_input, tokens_output, costo_estimado)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, modo, consulta,
             "## Analisis\nContenido de prueba.\n## Articulos citados\nArt. 1, Art. 2.\n## Limitaciones\nNinguna.",
             tiene_a, tiene_art, tiene_l,
             randint(1, 10), randint(4, 12), round(randint(0, 30) / 100, 2), randint(1, 4),
             round(randint(60, 99) / 100, 2), err_type, lat,
             randint(500, 3000), randint(200, 1500), round(randint(10, 300) / 10000, 4)),
        )

    # Insert daily metric with precise values
    con_error = total_q - exitosas
    error_rate = round(con_error / total_q * 100, 1)
    consistencia = round((exitosas * 0.7) / total_q * 100, 1) if exitosas > 0 else 0
    tok_in = randint(8000, 25000)
    tok_out = randint(4000, 12000)
    tok_total = tok_in + tok_out
    avg_tok = round(tok_total / total_q, 1)
    avg_cost = round(uniform(0.001, 0.015), 4)

    conn.execute(
        """INSERT OR REPLACE INTO metricas_diarias
           (fecha, total_consultas, exitosas, con_error,
            precision_pct, consistencia_pct, error_rate_pct, tiempo_promedio,
            tokens_input_total, tokens_output_total, tokens_total,
            avg_tokens_por_consulta, avg_costo_por_consulta)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (day_date.strftime("%Y-%m-%d"), total_q, exitosas, con_error,
         prec, consistencia, error_rate, avg_lat,
         tok_in, tok_out, tok_total, avg_tok, avg_cost),
    )

# ── Logs: scatter across last 7 days ──
modulos = ["app", "tools", "db", "api", "embeddings", "rag"]
for i in range(60):
    day_offset = randint(0, 6)
    ts = (today - timedelta(days=day_offset, hours=randint(0, 23),
                            minutes=randint(0, 59))).isoformat(timespec="seconds")
    nivel = choice(["INFO", "INFO", "INFO", "WARNING", "ERROR", "DEBUG"])
    modulo = choice(modulos)
    mensajes = {
        "INFO": "Consulta procesada correctamente",
        "WARNING": "Tiempo de respuesta alto (>5s)",
        "ERROR": "Error al conectar con API de OpenAI",
        "DEBUG": f"K={randint(3,15)}, temp={round(randint(0,50)/100,2)}",
    }
    conn.execute(
        "INSERT INTO logs (timestamp, nivel, modulo, mensaje) VALUES (?, ?, ?, ?)",
        (ts, nivel, modulo, mensajes[nivel]),
    )

conn.commit()

cur = conn.execute("SELECT COUNT(*) FROM consultas")
consultas = cur.fetchone()[0]
cur = conn.execute("SELECT COUNT(*) FROM logs")
logs = cur.fetchone()[0]
cur = conn.execute("SELECT COUNT(*) FROM metricas_diarias")
metricas = cur.fetchone()[0]
conn.close()

print(f"Seed complete: {consultas} consultas, {logs} logs, {metricas} metricas")
