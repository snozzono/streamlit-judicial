# ⚖️ Asistente Tributario — Bufete Ruiz Salazar

Agente conversacional con LangGraph para consultas de normativa tributaria chilena (DL-824, DL-825, DL-830 y circulares SII). El sistema integra herramientas de consulta, razonamiento y escritura en un flujo de trabajo organizacional con memoria de corto y largo plazo, más un **sistema de observabilidad (EP3)** para monitoreo de precisión, consistencia, latencia, errores y anomalías.

> ⚠️ Este asistente es orientativo. Las respuestas deben ser validadas por un contador o abogado tributario.

---

## Requisitos

- Python 3.10 – 3.13
- Token de [GitHub Models](https://github.com/marketplace/models) con acceso a Azure AI Inference

## Instalación

```bash
pip install -r requirements.txt
```

Crea `.env` en la raíz:

```
GH_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

Opcional — contraseña para el dashboard administrativo en `.streamlit/secrets.toml`:

```toml
[admin]
password = "tu_contraseña"
```

Si no se define, se usará la variable de entorno `ADMIN_PASSWORD`.

## Indexación (solo la primera vez)

Coloca los PDFs de normativa en `docs/` y ejecuta:

```bash
python indexar.py
```

Genera el vectorstore en `vectorstore/`. Output esperado:

```
=== Indexando corpus normativo ===
Total páginas cargadas: 483
Total chunks generados: 2399
Vectorstore guardado en 'vectorstore/'
=== Indexación completada ===
```

## Ejecución

```bash
streamlit run app.py
```

Disponible en `http://localhost:8501`.  
Dashboard administrativo en `http://localhost:8501/admin`.

---

## Arquitectura del agente (EP2)

### Diagrama de orquestación

```
                   ┌──────────────────────────────────────────────┐
                   │                EstadoAgente                   │
                   │  consulta · historial_mensajes (acumulado)    │
                   │  chunks_normativa · casos_similares           │
                   │  contexto_acumulado · evaluacion              │
                   │  iteraciones · modo · respuesta · ruta_memo   │
                   └──────────────────────────────────────────────┘

START
  │
  ▼
┌─────────────┐
│  classifier │  Detecta intención: "responder" | "memo"
└──────┬──────┘
       │  fan-out paralelo (Send)
       ├──────────────────────────────┐
       ▼                              ▼
┌──────────────────┐      ┌───────────────────────┐
│ buscar_normativa │      │    buscar_casos        │
│  FAISS DL-824    │      │  FAISS largo plazo     │
│  DL-825  DL-830  │      │  (sesiones anteriores) │
└────────┬─────────┘      └──────────┬────────────┘
         │       fan-in              │
         └─────────────┬─────────────┘
                       ▼
             ┌──────────────────┐
             │ evaluar_consulta │  LLM calcula confianza 0.0–1.0
             └────────┬─────────┘
                      │
         ┌────────────┼──────────────────┐
         │            │                  │
    confianza     modo=="memo"      confianza>=0.7
    <0.7 AND      confianza>=0.7    modo=="responder"
    iter<max           │                  │
         │             ▼                  ▼
         ▼      ┌─────────────┐    ┌───────────┐
    ┌─────────┐ │redactar_memo│    │ responder │
    │razonador│ │ genera .docx│    │ estructura│
    │(≤2 loops│ └──────┬──────┘    └─────┬─────┘
    └────┬────┘        │                 │
         │             └────────┬────────┘
         │ refinación           ▼
         └──────────► ┌──────────────┐
                      │   persistir  │  no-op en consultas normales;
                      └──────┬───────┘  app.py llama persistir_caso()
                             │          al cerrar sesión → anonimiza
                             ▼          y guarda en FAISS largo plazo
                            END
```

---

## Sistema de Observabilidad (EP3)

Se implementó un pipeline completo de monitoreo sobre el agente EP2, con métricas de precisión, consistencia, latencia, frecuencia de errores y consumo de tokens.

### Componentes

| Archivo | Rol |
|---|---|
| `monitor_db.py` | ORM SQLite + ETL diario + detección de anomalías + recomendaciones |
| `pages/admin.py` | Dashboard Streamlit con KPIs, gráficos, logs, anomalías |
| `seed_data.py` | Genera datos sintéticos de prueba (7 días con perfiles variados) |

### Métricas implementadas

| Métrica | Cálculo |
|---|---|
| **Precisión** | `(análisis_ok + artículos_ok + limitaciones_ok) / (total × 3) × 100` |
| **Consistencia** | `consultas_con_todas_las_secciones / total × 100` |
| **Tasa de error** | `consultas_con_error / total × 100` |
| **Latencia** | Promedio de `tiempo_ms` por día |
| **Tokens** | `tokens_input + tokens_output` por consulta, promediado por día |

### Dashboard

- **KPIs**: total consultas, tasa de error, precisión, consistencia, tiempo promedio, tokens
- **Métricas históricas**: gráficos de evolución diaria (líneas + barras)
- **Consultas**: listado paginado con filtro por modo y detalle expandible
- **Logs**: filtro por nivel (ERROR, WARNING, INFO, DEBUG)
- **Errores**: frecuencia y detalle de errores
- **Anomalías**: detección automática de picos de error, outliers de latencia, tendencia de precisión y patrones de fallo

### Anomalías detectadas

El sistema analiza los últimos 7 días y detecta:

| Tipo | Algoritmo |
|---|---|
| Picos de error | `error_rate > mean + 2σ` del período |
| Outliers de latencia | `tiempo_ms > mean + 3σ` del período |
| Tendencia de precisión | Pendiente de regresión lineal (mejorando/estable/empeorando) |
| Patrones de fallo | Errores agrupados por mensaje, ordenados por frecuencia |

### Recomendaciones

Basadas en los datos observados, el sistema genera sugerencias priorizadas (🔴 ALTA / 🟡 MEDIA / 🟢 BAJA) para optimizar errores, latencia, consumo de tokens, costos y precisión.

### Seed data

Para poblar el dashboard con datos de prueba:

```bash
python seed_data.py
```

Genera 105 consultas distribuidas en 7 días con perfiles variados (días normales, un pico de error y un día con latencia alta).

---

## Componentes

| Archivo | Rol |
|---|---|
| `config.py` | Parámetros centralizados: modelos, rutas, umbrales (`confianza_minima=0.7`, `max_reasoning_iterations=2`) |
| `anonymizer.py` | Anonimización de RUTs, emails, nombres y empresas antes de persistir en largo plazo |
| `memory.py` | `MemoriaCortoplazo` (buffer de mensajes por sesión) + `MemoriaLargoplazo` (FAISS de casos anteriores) |
| `tools.py` | 6 herramientas: `buscar_normativa`, `buscar_casos_anteriores`, `evaluar_consulta`, `redactar_memo`, `guardar_drive`, `enviar_gmail` |
| `graph.py` | Grafo LangGraph: 8 nodos, fan-out paralelo con `Send`, loop de razonamiento adaptativo |
| `indexar.py` | Indexación de PDFs → vectorstore FAISS (EP1, no modificar) |
| `app.py` | Interfaz Streamlit: pestaña EP2 conversacional + pestaña EP1 clásica |
| `monitor_db.py` | Sistema de monitoreo SQLite: consultas, logs, ETL diario, anomalías, recomendaciones |
| `pages/admin.py` | Dashboard administrativo con KPIs, gráficos y detección de anomalías |

---

## Flujo de una consulta

1. El usuario escribe una consulta en el chat (`st.chat_input`).
2. **`classifier`** determina el modo: detecta palabras clave como "memo" o "redactar" para activar la generación de documento.
3. **`buscar_normativa`** y **`buscar_casos`** se ejecutan en **paralelo** (fan-out via `Send`), consultando el vectorstore de normativa y el índice de casos anteriores simultáneamente.
4. **`evaluar_consulta`** usa un LLM secundario para calcular la confianza del contexto recuperado (0.0–1.0).
5. Si confianza < 0.7 y quedan iteraciones: **`razonador`** genera una consulta refinada, realiza una búsqueda adicional en FAISS y repite la evaluación (máximo 2 veces).
6. Si confianza ≥ 0.7: **`responder`** genera la respuesta estructurada (Análisis / Artículos citados / Limitaciones) o **`redactar_memo`** genera un `.docx` formal descargable.
7. Al hacer clic en **"Cerrar sesión"**, `app.py` llama `memoria_largo_plazo.persistir_caso()`: el historial es anonimizado (RUTs, nombres, empresas) y guardado en FAISS para mejorar futuras consultas similares.

---

## Decisiones de diseño

**LangGraph sobre LangChain Agents clásicos:** el grafo explícito con `StateGraph` permite controlar el loop de razonamiento con un tope configurable de iteraciones, evitando bucles infinitos y costos de API imprevistos.

**Fan-out paralelo:** `buscar_normativa` y `buscar_casos` no tienen dependencia entre sí. Ejecutarlos con `Send` en paralelo reduce la latencia de cada turno.

**Auto-evaluación de confianza:** `evaluar_consulta` implementa una forma de planificación adaptativa: el agente decide por sí mismo si necesita más contexto antes de responder, ajustando su comportamiento según las condiciones del entorno.

**Anonimización antes de persistir:** protección de datos personales en el índice de largo plazo usando un pipeline en dos pasos: regex (RUT, email, dirección) + LLM (nombres y razones sociales).

**Monitoreo integrado:** cada consulta y log se persiste en SQLite. El ETL diario computa métricas de precisión, consistencia y error. La detección de anomalías alerta sobre picos de error, outliers de latencia y tendencias negativas.

---

## Estructura de carpetas

```
├── docs/              ← PDFs de normativa (DL-824, DL-825, DL-830)
├── vectorstore/       ← index.faiss + index.pkl  (generado por indexar.py)
├── casos/             ← casos.index + casos.pkl  (generado al cerrar sesión)
├── memos/             ← memorándums .docx generados
├── data/              ← monitor.db (base de datos de monitoreo)
├── pages/
│   └── admin.py       ← Dashboard de observabilidad
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml   ← Contraseña admin (no versionado)
├── config.py
├── anonymizer.py
├── memory.py
├── tools.py
├── graph.py
├── indexar.py
├── app.py
├── monitor_db.py      ← Sistema de monitoreo (EP3)
├── seed_data.py       ← Datos de prueba para monitoreo
├── requirements.txt
└── .env               ← Token de API (no versionado)
```

## Stack tecnológico

| Tecnología | Versión | Uso |
|---|---|---|
| LangGraph | 0.2+ | Orquestación del agente (grafo de estados) |
| LangChain | 0.2+ | Abstracciones LLM, embeddings, FAISS |
| GitHub Models (Azure AI Inference) | — | `gpt-4o-mini` + `text-embedding-3-small` |
| FAISS | — | Vectorstore normativa y memoria de largo plazo |
| Streamlit | — | Interfaz de usuario + dashboard de monitoreo |
| SQLite | — | Base de datos de monitoreo (EP3) |
| python-docx | — | Generación de memorándums Word |

---

## Pruebas

```bash
pytest test_unit.py        # tests unitarios
pytest test_admin.py       # tests del sistema de monitoreo (16 tests)
pytest test_queries.py     # validación de consultas de ejemplo
```

Seed data para el dashboard:

```bash
python seed_data.py        # Pobla data/monitor.db con 105 consultas de prueba
```

---

## Referencias

- LangChain Inc. (2024). *LangGraph: Build stateful, multi-actor applications with LLMs*. https://langchain-ai.github.io/langgraph/
- LangChain Inc. (2024). *LangChain Python Documentation*. https://python.langchain.com/docs/
- Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., … Kiela, D. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. arXiv:2005.11401. https://arxiv.org/abs/2005.11401
- Johnson, J., Douze, M., & Jégou, H. (2019). *Billion-scale similarity search with GPUs*. IEEE Transactions on Big Data, 7(3), 535–547. https://doi.org/10.1109/TBDATA.2019.2921572
- Servicio de Impuestos Internos de Chile. (2024). *Decreto Ley N°824 — Ley sobre Impuesto a la Renta*. https://www.sii.cl
- Servicio de Impuestos Internos de Chile. (2024). *Decreto Ley N°825 — Ley sobre Impuesto a las Ventas y Servicios*. https://www.sii.cl
- Servicio de Impuestos Internos de Chile. (2024). *Decreto Ley N°830 — Código Tributario*. https://www.sii.cl

---

Proyecto académico — Ingeniería de Soluciones con IA (ISY0101), DuocUC 2025.
