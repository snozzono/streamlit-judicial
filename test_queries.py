"""
test_queries.py — Validación automática del pipeline RAG

Uso:
    python test_queries.py

Salida:
    - Consola: resumen por consulta con PASS/FAIL
    - test_results.md: informe completo con respuestas y detalle de validaciones

Exit codes:
    0 — todas las validaciones pasaron
    1 — al menos una validación falló (útil para CI)
"""

import logging
import os
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import FAISS

from config import CONFIG
from utils import (
    SYSTEM_PROMPT,
    get_embeddings,
    get_llm,
    get_prompt_template,
    parsear_respuesta,
)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")

load_dotenv()

RESULTS_FILE = "test_results.md"
K = CONFIG.k_default
TEMPERATURE = CONFIG.temperature_default

API_KEY = os.getenv("GITHUB_TOKEN")
if not API_KEY:
    print("❌ GITHUB_TOKEN no encontrado en variables de entorno.")
    sys.exit(1)

# ── CONSULTAS DE PRUEBA ───────────────────────────────────────────────────────
# (id, categoria, consulta, espera_sin_cobertura)
# espera_sin_cobertura=True: el modelo debe indicar que el tema está fuera del corpus
CONSULTAS = [
    (
        "T01",
        "DL 825 — IVA",
        "¿Qué actividades están exentas de IVA según el artículo 12?",
        False,
    ),
    (
        "T02",
        "DL 825 — IVA",
        "¿Cuál es la tasa general del IVA y en qué casos se aplica una tasa diferenciada?",
        False,
    ),
    (
        "T03",
        "DL 824 — Renta",
        "¿Qué se entiende por renta según el DL 824 y qué rentas están exentas?",
        False,
    ),
    (
        "T04",
        "DL 824 — Renta",
        "¿Cómo se determina la base imponible del impuesto de primera categoría?",
        False,
    ),
    (
        "T05",
        "DL 830 — Código Tributario",
        "¿Cuáles son los plazos de prescripción de la acción del SII para cobrar impuestos?",
        False,
    ),
    (
        "T06",
        "DL 830 — Código Tributario",
        "¿Qué sanciones contempla el Código Tributario para la declaración maliciosamente falsa?",
        False,
    ),
    (
        "T07",
        "Caso borde — fuente externa",
        "¿Qué obligaciones tributarias tiene una empresa extranjera sin domicilio en Chile "
        "que presta servicios digitales?",
        False,
    ),
    (
        "T08",
        "Caso borde — incumplimiento",
        "¿Qué pasa si un contribuyente no presenta su declaración de impuestos dentro del plazo?",
        False,
    ),
    (
        "T09",
        "Fuera de corpus",
        "¿Cuáles son los requisitos para obtener una visa de trabajo en Chile?",
        True,
    ),
]


# ── VALIDACIONES ──────────────────────────────────────────────────────────────
def validar(secciones: dict[str, str], fuentes: list, espera_sin_cobertura: bool) -> list[dict]:
    resultados = []

    # V1: Análisis no vacío
    ok = bool(secciones["analisis"].strip())
    resultados.append(
        {
            "nombre": "Análisis no vacío",
            "passed": ok,
            "detalle": "" if ok else "La sección ## Análisis está vacía.",
        }
    )

    # V2: Artículos citados
    if espera_sin_cobertura:
        ok = not bool(secciones["articulos"].strip()) or secciones["articulos"].strip().lower() == "no aplica"
        resultados.append(
            {
                "nombre": "Sin artículos inventados (fuera de corpus)",
                "passed": ok,
                "detalle": "" if ok else "Se esperaba respuesta sin artículos pero el modelo citó normativa.",
            }
        )
    else:
        ok = bool(secciones["articulos"].strip())
        resultados.append(
            {
                "nombre": "Al menos un artículo citado",
                "passed": ok,
                "detalle": "" if ok else "La sección ## Artículos citados está vacía.",
            }
        )

    # V3: Sección limitaciones presente (siempre requerida)
    ok = bool(secciones["limitaciones"].strip())
    resultados.append(
        {
            "nombre": "Sección Limitaciones presente",
            "passed": ok,
            "detalle": "" if ok else "La sección ## Limitaciones está vacía.",
        }
    )

    # V4: Fragmentos fuente recuperados
    ok = len(fuentes) > 0
    resultados.append(
        {
            "nombre": "Fragmentos fuente recuperados",
            "passed": ok,
            "detalle": "" if ok else "El retriever no devolvió ningún fragmento.",
        }
    )

    return resultados


# ── SETUP DEL PIPELINE ────────────────────────────────────────────────────────
def construir_chain() -> RetrievalQA:
    print("Cargando vectorstore...")
    embeddings = get_embeddings(API_KEY)
    vectorstore = FAISS.load_local(
        CONFIG.vectorstore_dir,
        embeddings,
        allow_dangerous_deserialization=True,
    )
    llm = get_llm(API_KEY, TEMPERATURE)
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": K},
    )
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": get_prompt_template()},
        return_source_documents=True,
    )


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main() -> None:
    chain = construir_chain()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_pass = 0
    total_fail = 0
    registros: list[dict] = []

    print(f"\n{'='*60}")
    print(f"  Test suite — {timestamp}")
    print(f"  k={K}  temp={TEMPERATURE}  consultas={len(CONSULTAS)}")
    print(f"{'='*60}\n")

    for tid, categoria, consulta, sin_cobertura in CONSULTAS:
        print(f"[{tid}] {consulta[:70]}...")

        t0 = time.time()
        try:
            resultado = chain.invoke({"query": consulta})
            elapsed = time.time() - t0
            respuesta = resultado["result"]
            fuentes = resultado["source_documents"]
            secciones = parsear_respuesta(respuesta)
            validaciones = validar(secciones, fuentes, sin_cobertura)

            fallos = [v for v in validaciones if not v["passed"]]
            passed = len(fallos) == 0

            estado = "✅ PASS" if passed else f"❌ FAIL ({len(fallos)} checks)"
            print(f"     {estado}  |  {elapsed:.1f}s  |  fuentes={len(fuentes)}")
            for f in fallos:
                print(f"     → {f['nombre']}: {f['detalle']}")

            total_pass += int(passed)
            total_fail += int(not passed)

            registros.append(
                {
                    "tid": tid,
                    "categoria": categoria,
                    "consulta": consulta,
                    "secciones": secciones,
                    "fuentes": fuentes,
                    "validaciones": validaciones,
                    "elapsed": elapsed,
                    "passed": passed,
                    "error": None,
                }
            )

        except Exception as exc:
            elapsed = time.time() - t0
            print(f"     💥 ERROR: {exc}")
            total_fail += 1
            registros.append(
                {
                    "tid": tid,
                    "categoria": categoria,
                    "consulta": consulta,
                    "secciones": {},
                    "fuentes": [],
                    "validaciones": [],
                    "elapsed": elapsed,
                    "passed": False,
                    "error": str(exc),
                }
            )

    # ── RESUMEN CONSOLA ───────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Resultado: {total_pass} PASS  /  {total_fail} FAIL  de {len(CONSULTAS)} consultas")
    print(f"{'='*60}\n")

    # ── GENERAR test_results.md ───────────────────────────────────────────────
    lineas = [
        "# Test Results — Asistente Tributario RAG",
        "",
        f"**Fecha:** {timestamp}  ",
        f"**Parámetros:** k={K}, temperatura={TEMPERATURE}  ",
        f"**Resultado global:** {total_pass} PASS / {total_fail} FAIL de {len(CONSULTAS)} consultas",
        "",
        "---",
        "",
    ]

    for r in registros:
        estado_md = "✅ PASS" if r["passed"] else "❌ FAIL"
        lineas += [
            f"## [{r['tid']}] {estado_md} — {r['categoria']}",
            "",
            f"**Consulta:** {r['consulta']}  ",
            f"**Tiempo:** {r['elapsed']:.1f}s  |  **Fragmentos recuperados:** {len(r['fuentes'])}",
            "",
        ]

        if r["error"]:
            lineas += [f"**Error:** `{r['error']}`", ""]
        else:
            lineas.append("**Validaciones:**")
            for v in r["validaciones"]:
                icono = "✅" if v["passed"] else "❌"
                detalle = f" — {v['detalle']}" if not v["passed"] else ""
                lineas.append(f"- {icono} {v['nombre']}{detalle}")
            lineas.append("")

            if r["secciones"].get("analisis"):
                lineas += ["**Análisis:**", r["secciones"]["analisis"], ""]
            if r["secciones"].get("articulos"):
                lineas += ["**Artículos citados:**", r["secciones"]["articulos"], ""]
            if r["secciones"].get("limitaciones"):
                lineas += ["**Limitaciones:**", r["secciones"]["limitaciones"], ""]

            if r["fuentes"]:
                lineas.append("**Fuentes:**")
                for i, doc in enumerate(r["fuentes"], 1):
                    nombre = os.path.basename(doc.metadata.get("source", "desconocida"))
                    pagina = doc.metadata.get("page", "?")
                    lineas.append(f"- Fragmento {i}: {nombre}, pág. {pagina}")
                lineas.append("")

        lineas.append("---")
        lineas.append("")

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    print(f"Resultados guardados en '{RESULTS_FILE}'")
    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
