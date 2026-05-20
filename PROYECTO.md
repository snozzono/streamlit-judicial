# EP2 — Agente Tributario con LangGraph

**Asignatura:** ISY0101 Optativo Ingeniería de Soluciones con IA  
**Bufete:** Ruiz Salazar Tributaria  
**Integrantes:** Martín Higuera · Gustavo Oporto  
**Entrega:** 28 de mayo 2026

---

## Contexto del problema

El bufete Ruiz Salazar Tributaria enfrenta una dependencia crítica en la búsqueda manual de normativa tributaria chilena. Los abogados invierten tiempo significativo consultando cuerpos legales dispersos (DL-824, DL-825, DL-830, circulares SII) para responder consultas de clientes y redactar memorándums de análisis. El proceso es lento, propenso a omisiones y no escala con el volumen de casos.

La EP1 resolvió la consulta puntual con un RAG básico. La EP2 extiende eso hacia un **agente funcional** capaz de razonar sobre varias búsquedas, mantener coherencia en sesiones prolongadas y generar documentos formales.

---

## Qué se construyó en EP2

| Componente | Descripción |
|---|---|
| `graph.py` | Grafo LangGraph con 8 nodos, fan-out paralelo y loop de razonamiento |
| `tools.py` | 4 herramientas del agente: búsqueda normativa, búsqueda de casos, evaluación de contexto y generación de memo |
| `memory.py` | Memoria dual: buffer de sesión (corto plazo) + índice FAISS de casos anonimizados (largo plazo) |
| `anonymizer.py` | Pipeline de anonimización en dos pasos: regex (RUT, email, dirección) + LLM (nombres, empresas) |
| `app.py` | Interfaz Streamlit extendida con chat conversacional, generación de memo y cierre de sesión persistente |

---

## Arquitectura del grafo

El agente se implementa como un `StateGraph` de LangGraph. El estado compartido entre nodos es un `TypedDict` con los siguientes campos:

```
consulta            str       — input del usuario en el turno actual
historial_mensajes  list      — mensajes acumulados entre turnos (reducer: add)
chunks_normativa    list      — fragmentos recuperados del vectorstore
casos_similares     list      — casos anteriores recuperados del índice largo plazo
contexto_acumulado  str       — contexto consolidado para el LLM
evaluacion          dict      — {cubierta, confianza, accion_sugerida}
iteraciones         int       — contador del loop de razonamiento
modo                str       — "responder" | "memo"
respuesta           str       — output final al usuario
ruta_memo           str|None  — ruta del .docx generado
```

### Nodos

| Nodo | Rol |
|---|---|
| `classifier` | Detecta la intención: modo `memo` si la consulta contiene palabras clave como "redactar", "memorándum", "informe formal"; modo `responder` en otro caso |
| `buscar_normativa` | Busca los k fragmentos más relevantes en el vectorstore FAISS de normativa (DL-824, DL-825, DL-830) |
| `buscar_casos` | Recupera los 3 casos más similares del índice FAISS de largo plazo |
| `evaluar_consulta` | Llama al LLM con el contexto acumulado y obtiene `confianza` (0.0–1.0) y `accion_sugerida` |
| `razonador` | Si la confianza es insuficiente, genera una consulta refinada, ejecuta una búsqueda adicional y re-evalúa. Máximo 2 iteraciones |
| `responder` | Genera la respuesta estructurada (Análisis / Artículos citados / Limitaciones) usando el contexto completo e historial de la sesión |
| `generar_informe` | Genera el análisis jurídico y produce un `.docx` formal en `memos/`, descargable desde la interfaz |
| `persistir` | No-op durante consultas normales. La persistencia real se dispara desde `app.py` al cerrar sesión |

### Flujo de ejecución

```
START → classifier
      → buscar_normativa  ┐  (paralelo via Send)
      → buscar_casos      ┘
      → evaluar_consulta
      → razonador            si confianza < 0.7 AND iteraciones < 2
        └→ evaluar_consulta  (loop)
      → generar_informe      si modo == "memo" AND confianza ≥ 0.7
      → responder            si modo == "responder" AND confianza ≥ 0.7
      → persistir → END
```

### Decisiones de diseño clave

**Fan-out paralelo:** `buscar_normativa` y `buscar_casos` no tienen dependencia entre sí. Se despachan con `Send` en el mismo super-step de LangGraph y sus actualizaciones de estado se fusionan automáticamente antes de `evaluar_consulta`, reduciendo la latencia de cada turno.

**Loop de razonamiento acotado:** El nodo `razonador` implementa un loop hacia `evaluar_consulta` con un tope de `CONFIG.max_reasoning_iterations = 2`. Esto evita bucles infinitos y costos de API imprevistos, al mismo tiempo que permite una búsqueda adaptativa cuando el contexto inicial es insuficiente.

**Auto-evaluación de confianza:** `evaluar_consulta` usa un LLM secundario (temperatura 0) para estimar qué tan bien el contexto cubre la consulta antes de responder. Esto implementa planificación adaptativa: el agente decide por sí mismo si necesita más información o puede responder.

**Anonimización antes de persistir:** El índice de largo plazo nunca almacena datos sensibles. El pipeline de anonimización aplica regex (RUT, email, dirección) y luego LLM (nombres, razones sociales) antes de vectorizar cada caso.

---

## Memoria

### Corto plazo

Lista de objetos `BaseMessage` (langchain_core) acumulada durante la sesión activa. Se inyecta en los nodos `razonador` y `responder` para mantener coherencia entre turnos. Se destruye al cerrar la sesión o iniciar una nueva.

### Largo plazo

Índice FAISS persistido en `casos/casos.index` + `casos/casos.pkl`. Se actualiza al cierre de sesión mediante `MemoriaLargoplazo.persistir_caso()`:

1. El texto completo de la sesión se anonimiza con `anonymizer.anonimizar()`
2. El texto anonimizado se vectoriza con `text-embedding-3-small`
3. El vector se agrega al índice FAISS y se guarda a disco

En turnos futuros, `buscar_casos` recupera casos similares por similitud semántica, enriqueciendo el contexto del agente con precedentes relevantes.

---

## Herramientas del agente

| Tool | Input | Output |
|---|---|---|
| `buscar_normativa(query, k)` | Consulta en lenguaje natural | Lista de `Document` con fragmentos de DL-824, DL-825, DL-830 y metadata de fuente/página |
| `buscar_casos_anteriores(query, k)` | Consulta en lenguaje natural | Lista de `Document` con casos anteriores anonimizados |
| `evaluar_consulta(consulta, contexto)` | Consulta + contexto acumulado | `{cubierta: bool, confianza: float, accion_sugerida: str}` |
| `generar_informe(caso, contexto, analisis, destinatario)` | Datos del caso y análisis | Ruta del `.docx` generado en `memos/` |

---

## Interfaz de usuario

La app Streamlit se organiza en dos pestañas:

**Conversacional (EP2):** Chat con `st.chat_input` / `st.chat_message`. Cada mensaje invoca el grafo LangGraph completo. El historial visual y el buffer de memoria de corto plazo se mantienen en `st.session_state`. Al hacer clic en **Generar memo** se solicita confirmación antes de invocar `generar_informe`; el `.docx` resultante queda disponible para descarga directa desde la interfaz. El botón **Cerrar sesión** persiste el caso en el índice de largo plazo y bloquea el input hasta iniciar una nueva sesión.

**Consulta clásica (EP1):** Interfaz original con `st.text_area`, sliders de k y temperatura, visualización de fuentes y exportación de historial a JSON. Sin cambios respecto a la EP1.

---

## Pruebas

Suite de 9 casos en `test_queries.py`. Cada caso valida que la respuesta contenga las tres secciones requeridas (Análisis, Artículos citados, Limitaciones) y cite al menos un artículo del corpus correspondiente.

| ID | Consulta | Corpus | Resultado |
|---|---|---|---|
| T01 | Impuesto de primera categoría | DL-824 | PASS |
| T02 | Tasa IVA y tasa diferenciada | DL-825 | FAIL — k insuficiente para corpus DL-825 |
| T03 | Exenciones IVA | DL-825 | PASS |
| T04 | Prescripción tributaria | DL-830 | PASS |
| T05 | Gastos necesarios para producir renta | DL-824 | PASS |
| T06 | Sanciones por no declarar | DL-830 | PASS |
| T07 | Impuesto adicional para extranjeros | DL-824 | PASS |
| T08 | Pregunta fuera del corpus tributario | — | PASS |
| T09 | Visa de trabajo (fuera de corpus) | — | FAIL — sección Limitaciones incompleta |

**7/9 PASS.** Los dos fallos son estructurales en el output, no errores de razonamiento. El sistema no generó artículos inventados en ningún caso.

---

## Stack

| Tecnología | Uso |
|---|---|
| LangGraph 0.2+ | Orquestación del agente |
| LangChain 0.2+ | Abstracciones LLM, embeddings, FAISS |
| GitHub Models (Azure AI Inference) | `gpt-4o-mini` + `text-embedding-3-small` |
| FAISS | Vectorstore normativa y casos |
| Streamlit | Interfaz web |
| python-docx | Generación de memorándums |
| python-dotenv | Variables de entorno |

---

## Diferencias respecto a EP1

| Aspecto | EP1 | EP2 |
|---|---|---|
| Arquitectura | Chain `RetrievalQA` | Grafo LangGraph con 8 nodos |
| Memoria | Sin memoria entre turnos | Corto plazo (sesión) + largo plazo (FAISS persistente) |
| Razonamiento | Un solo paso de recuperación | Loop adaptativo con auto-evaluación de confianza |
| Output | Respuesta de texto | Respuesta de texto + memorándum `.docx` descargable |
| Interfaz | Consulta con botón | Chat conversacional con gestión de sesión |
| Privacidad | No aplica | Anonimización antes de persistir casos |
