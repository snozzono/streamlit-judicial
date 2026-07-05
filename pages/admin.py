import os
import time
from datetime import date, datetime, timedelta

import streamlit as st

from monitor_db import get_monitor

st.set_page_config(
    page_title="Dashboard — Monitor Tributario",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .card {
        background: #f8f9fa;
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 1rem;
    }
    .card-alert {
        background: #ffebee;
        border-left: 4px solid #d32f2f;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
    }
    .card-warn {
        background: #fff8e1;
        border-left: 4px solid #f57c00;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
    }
    .badge-alta { background: #d32f2f; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
    .badge-media { background: #f57c00; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
    .badge-baja { background: #388e3c; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: bold; }
    .login-box {
        max-width: 400px; margin: 4rem auto; padding: 2rem;
        background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        text-align: center;
    }
    .stMetric { background: white; border-radius: 10px; padding: 0.8rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

ADMIN_PASSWORD = st.secrets.get("admin", {}).get("password") or os.getenv("ADMIN_PASSWORD", "admin123")

# ── Rate limiting ──────────────────────────────────────────────────────────────

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900  # 15 min


def _check_lockout() -> tuple[bool, int | None]:
    """Returns (is_locked, seconds_remaining)."""
    attempts = st.session_state.get("login_attempts", 0)
    lock_time = st.session_state.get("login_lock_time")
    if attempts >= MAX_LOGIN_ATTEMPTS and lock_time:
        elapsed = time.time() - lock_time
        if elapsed < LOGIN_LOCKOUT_SECONDS:
            return True, int(LOGIN_LOCKOUT_SECONDS - elapsed)
        _reset_login_attempts()
    return False, None


def _register_failed_attempt():
    st.session_state.login_attempts = st.session_state.get("login_attempts", 0) + 1
    if st.session_state.login_attempts >= MAX_LOGIN_ATTEMPTS:
        st.session_state.login_lock_time = time.time()


def _reset_login_attempts():
    st.session_state.login_attempts = 0
    st.session_state.login_lock_time = None


def autenticar() -> bool:
    if st.session_state.get("admin_auth"):
        return True
    token = st.query_params.get("auth")
    if token == "1":
        st.session_state.admin_auth = True
        return True

    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.image("https://cdn.jsdelivr.net/npm/streamlit@1/dist/favicon.png", width=64)
    st.title("Panel de Monitoreo")
    st.caption("Acceso restringido — Bufete Ruiz Salazar")

    locked, remaining = _check_lockout()
    if locked:
        mins, secs = divmod(remaining, 60)
        st.warning(f"⛔ Cuenta bloqueada por demasiados intentos fallidos. Intenta de nuevo en **{mins}m {secs}s**.")
        st.markdown('</div>', unsafe_allow_html=True)
        return False

    attempts_left = MAX_LOGIN_ATTEMPTS - st.session_state.get("login_attempts", 0)
    password = st.text_input(
        "Contraseña:", type="password", label_visibility="collapsed",
        placeholder="Ingrese contraseña",
    )
    if st.button("Ingresar", type="primary", use_container_width=True):
        if password and password == ADMIN_PASSWORD:
            _reset_login_attempts()
            st.session_state.admin_auth = True
            st.query_params["auth"] = "1"
            st.rerun()
        else:
            _register_failed_attempt()
            remaining = MAX_LOGIN_ATTEMPTS - st.session_state.get("login_attempts", 0)
            if remaining > 0:
                st.error(f"Contraseña incorrecta. Te quedan **{remaining}** intento(s).")
            else:
                st.error("Contraseña incorrecta. Cuenta bloqueada por 15 minutos.")
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    return False


if not autenticar():
    st.stop()

monitor = get_monitor()

col_title, col_logout = st.columns([5, 1])
with col_title:
    st.title("📊 Dashboard de Monitoreo")
    st.caption("Precisión · Consistencia · Latencia · Errores · Trazabilidad")
with col_logout:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.admin_auth = False
        st.query_params.clear()
        st.rerun()

st.sidebar.header("🔧 Controles")
if st.sidebar.button("🔄 Ejecutar ETL (hoy)", use_container_width=True):
    with st.spinner("Ejecutando pipeline ETL..."):
        res = monitor.etl_ejecutar()
        if res.get("total", 0) > 0:
            st.sidebar.success(f"ETL ejecutado: {res['total']} consultas, precisión {res['precision_pct']}%, error {res['error_rate_pct']}%")
        else:
            st.sidebar.info("Sin datos para hoy.")

if st.sidebar.button("📥 Cargar datos de prueba", use_container_width=True):
    with st.spinner("Generando datos sintéticos..."):
        import subprocess, sys
        result = subprocess.run([sys.executable, "seed_data.py"], capture_output=True, text=True)
        if result.returncode == 0:
            st.sidebar.success("✅ Datos de prueba cargados. Ejecuta ETL para verlos.")
        else:
            st.sidebar.error(f"❌ Error: {result.stderr[:200]}")

if st.sidebar.button("🔄 Ejecutar ETL (todo)", use_container_width=True):
    with st.spinner("Procesando todas las fechas..."):
        fechas = set()
        for c in monitor.obtener_consultas(limite=10000):
            fechas.add(c["timestamp"][:10])
        for f in sorted(fechas):
            monitor.etl_ejecutar(f)
        st.sidebar.success(f"ETL ejecutado para {len(fechas)} días.")

st.sidebar.markdown("---")
st.sidebar.header("💡 Recomendaciones")
try:
    for r in (monitor.recomendar_optimizaciones() or []):
        badge = {"alta": '<span class="badge-alta">ALTA</span>',
                 "media": '<span class="badge-media">MEDIA</span>',
                 "baja": '<span class="badge-baja">BAJA</span>'}.get(r.get("prioridad", "baja"), "")
        st.sidebar.markdown(f'{badge} **{r.get("area","").upper()}**<br>{r.get("recomendacion", r.get("problema", ""))[:100]}', unsafe_allow_html=True)
except Exception:
    st.sidebar.info("No hay recomendaciones disponibles.")

resumen = monitor.obtener_resumen()
ultimas_m = resumen.get("ultimas_metricas")

kpi_data = [
    ("Total consultas", resumen["total_consultas"], None),
    ("Tasa de error", f'{resumen["tasa_error_pct"]}%', "inverse" if resumen["tasa_error_pct"] > 10 else "normal"),
    ("Precisión (hoy)", f'{ultimas_m["precision_pct"]}%' if ultimas_m else "—", None),
    ("Consistencia (hoy)", f'{ultimas_m["consistencia_pct"]}%' if ultimas_m else "—", None),
    ("Tiempo promedio", f'{ultimas_m["tiempo_promedio"]:.0f}ms' if ultimas_m else "—", None),
]

cols = st.columns(5)
for i, (label, val, delta_color) in enumerate(kpi_data):
    with cols[i]:
        kwargs = {"delta_color": delta_color} if delta_color else {}
        st.metric(label, val, **kwargs)

if "tokens_total" in (ultimas_m or {}):
    cols2 = st.columns(4)
    with cols2[0]:
        st.metric("Tokens usados (hoy)", ultimas_m.get("tokens_total", "—"))
    with cols2[1]:
        st.metric("Avg tokens/consulta", ultimas_m.get("avg_tokens_por_consulta", "—"))
    with cols2[2]:
        st.metric("Tokens input", ultimas_m.get("tokens_input_total", "—"))
    with cols2[3]:
        st.metric("Tokens output", ultimas_m.get("tokens_output_total", "—"))

st.markdown("---")

try:
    alertas = monitor.verificar_alertas()
    num_alertas = len(alertas)
except Exception:
    alertas = []
    num_alertas = 0

tab_names = [
    "📈 Métricas históricas",
    "📋 Consultas",
    "📝 Logs",
    "❌ Errores",
    "🔍 Anomalías",
    f"🚨 Alertas ({num_alertas})" if num_alertas else "🚨 Alertas",
]
tab_metricas, tab_consultas, tab_logs, tab_errores, tab_anomalias, tab_alertas = st.tabs(tab_names)

# ═══════════════════════════════════════════════
# TAB: Métricas
# ═══════════════════════════════════════════════

with tab_metricas:
    metricas = monitor.obtener_metricas(dias=30)
    if not metricas:
        st.info("No hay métricas diarias. Ejecuta el ETL desde el panel izquierdo.")
    else:
        metricas.sort(key=lambda m: m["fecha"])
        st.subheader("📈 Evolución diaria")
        chart_data = {
            "fecha": [m["fecha"] for m in metricas],
            "Precisión (%)": [m["precision_pct"] for m in metricas],
            "Consistencia (%)": [m["consistencia_pct"] for m in metricas],
            "Tasa error (%)": [m["error_rate_pct"] for m in metricas],
        }
        y_cols = ["Precisión (%)", "Consistencia (%)", "Tasa error (%)"]
        if "tokens_total" in metricas[0]:
            chart_data["Tokens totales"] = [m["tokens_total"] for m in metricas]
            y_cols.append("Tokens totales")
        if "avg_tokens_por_consulta" in metricas[0]:
            chart_data["Avg tokens"] = [m["avg_tokens_por_consulta"] for m in metricas]
            y_cols.append("Avg tokens")
        st.line_chart(chart_data, x="fecha", y=y_cols)

        vol_data = {
            "fecha": [m["fecha"] for m in metricas],
            "Consultas": [m["total_consultas"] for m in metricas],
            "Exitosas": [m["exitosas"] for m in metricas],
        }
        st.subheader("📊 Volumen diario")
        st.bar_chart(vol_data, x="fecha", y=["Consultas", "Exitosas"])

        st.subheader("📋 Detalle por día")
        detalle = [
            {
                "Fecha": m["fecha"],
                "Consultas": m["total_consultas"],
                "Exitosas": m["exitosas"],
                "Errores": m["con_error"],
                "Precisión": f'{m["precision_pct"]}%',
                "Consistencia": f'{m["consistencia_pct"]}%',
                "Tasa error": f'{m["error_rate_pct"]}%',
                "Tiempo prom.": f'{m["tiempo_promedio"]:.0f}ms',
            }
            for m in reversed(metricas)
        ]
        st.dataframe(detalle, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════
# TAB: Consultas
# ═══════════════════════════════════════════════

with tab_consultas:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        modo_filter = st.selectbox("Filtrar por modo", ["Todos", "EP1", "EP2"])
    with col_f2:
        num_consultas = st.number_input("Mostrar", min_value=10, max_value=500, value=50, step=10)

    consultas = monitor.obtener_consultas(
        limite=num_consultas, modo=None if modo_filter == "Todos" else modo_filter,
    )
    if not consultas:
        st.info("No hay consultas registradas.")
    else:
        rows = []
        for c in consultas:
            rows.append({
                "ID": c["id"],
                "Hora": c["timestamp"][11:19],
                "Modo": c["modo"],
                "Consulta": c["consulta"][:60] + ("..." if len(c["consulta"]) > 60 else ""),
                "Análisis": "✅" if c["tiene_analisis"] else "❌",
                "Artículos": "✅" if c["tiene_articulos"] else "❌",
                "Limitaciones": "✅" if c["tiene_limitaciones"] else "❌",
                "Fuentes": c["num_fuentes"],
                "Tiempo": f'{c["tiempo_ms"]:.0f}ms' if c["tiempo_ms"] else "-",
                "Error": "⚠️" if c["error"] else "✅",
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

        consulta_id = st.number_input("Ver detalle de consulta por ID:", min_value=1, step=1)
        if consulta_id:
            detalle = monitor.obtener_consulta(consulta_id)
            if detalle:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**Consulta:** {detalle['consulta']}")
                    st.markdown(f"**Modo:** {detalle['modo']}  ·  **Timestamp:** {detalle['timestamp']}")
                    if detalle["k_usado"]: st.markdown(f"**K:** {detalle['k_usado']}")
                    if detalle["temperatura"]: st.markdown(f"**Temperatura:** {detalle['temperatura']}")
                    if detalle["iteraciones"]: st.markdown(f"**Iteraciones:** {detalle['iteraciones']}")
                    if detalle.get("confianza"): st.markdown(f"**Confianza:** {detalle['confianza']}")
                with col_b:
                    st.markdown(f"**Análisis:** {'✅' if detalle['tiene_analisis'] else '❌'}")
                    st.markdown(f"**Artículos:** {'✅' if detalle['tiene_articulos'] else '❌'}")
                    st.markdown(f"**Limitaciones:** {'✅' if detalle['tiene_limitaciones'] else '❌'}")
                    st.markdown(f"**Fuentes:** {detalle['num_fuentes']}  ·  **Tiempo:** {detalle['tiempo_ms']:.0f}ms")
                if detalle.get("respuesta"):
                    with st.expander("Ver respuesta completa"):
                        st.text(detalle["respuesta"])
                if detalle.get("error"):
                    st.error(f"Error: {detalle['error']}")
            else:
                st.warning(f"No se encontró consulta con ID {consulta_id}.")

# ═══════════════════════════════════════════════
# TAB: Logs
# ═══════════════════════════════════════════════

with tab_logs:
    nivel_filter = st.selectbox("Filtrar por nivel", ["Todos", "ERROR", "WARNING", "INFO", "DEBUG"])
    logs = monitor.obtener_logs(limite=200, nivel=None if nivel_filter == "Todos" else nivel_filter)
    if not logs:
        st.info("No hay logs registrados.")
    else:
        color_map = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🟢", "DEBUG": "🔵"}
        rows_log = [{
            "Hora": l["timestamp"][11:19],
            "Nivel": f"{color_map.get(l['nivel'], '⚪')} {l['nivel']}",
            "Módulo": l.get("modulo", ""),
            "Mensaje": l["mensaje"][:120] + ("..." if len(l["mensaje"]) > 120 else ""),
        } for l in logs]
        st.dataframe(rows_log, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════
# TAB: Errores
# ═══════════════════════════════════════════════

with tab_errores:
    errores = [e for e in monitor.obtener_consultas(limite=200) if e["error"]]
    if not errores:
        st.success("🎉 No hay errores registrados.")
    else:
        st.error(f"⚠️ {len(errores)} consultas con error.")
        from collections import Counter
        tipos_error = Counter(e["error"][:60] for e in errores)
        st.subheader("📊 Frecuencia de errores")
        err_data = {"Error": [k for k, _ in tipos_error.most_common(10)],
                    "Frecuencia": [v for _, v in tipos_error.most_common(10)]}
        st.bar_chart(err_data, x="Error", y="Frecuencia")
        st.subheader("📋 Detalle de errores")
        rows_err = [{"ID": e["id"], "Hora": e["timestamp"][11:19], "Modo": e["modo"],
                      "Consulta": e["consulta"][:60], "Error": e["error"][:100]}
                     for e in errores[:100]]
        st.dataframe(rows_err, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════
# TAB: Anomalías
# ═══════════════════════════════════════════════

with tab_anomalias:
    try:
        anomalias = monitor.detectar_anomalias()
    except Exception as e:
        anomalias = None
        st.error(f"Error en detección de anomalías: {e}")

    if anomalias is None:
        st.info("Módulo de detección de anomalías no disponible.")
    else:
        st.subheader("🚨 Picos de error")
        spikes = anomalias.get("picos_error", [])
        if spikes:
            for s in spikes:
                st.markdown(f'<div class="card-alert"><strong>{s.get("fecha","?")}</strong> — Tasa error: {s.get("error_rate_pct","?")}% <small>(umbral: {s.get("threshold","?")}%)</small></div>', unsafe_allow_html=True)
        else:
            st.success("✅ No se detectaron picos de error.")

        st.subheader("⏱️ Outliers de latencia")
        outliers = anomalias.get("picos_latencia", [])
        if outliers:
            for o in outliers:
                ts = o.get("timestamp","?")[11:19] if o.get("timestamp") else "?"
                st.markdown(f'<div class="card-warn"><strong>{ts}</strong> — ID {o.get("id","?")} — {o.get("tiempo_ms",0):.0f}ms<br><small>{o.get("consulta","")[:60]}</small></div>', unsafe_allow_html=True)
        else:
            st.success("✅ No se detectaron outliers de latencia.")

        st.subheader("📈 Tendencia de precisión")
        trend = anomalias.get("tendencia_precision", "estable")
        icon = {"mejorando": "🟢", "estable": "🔵", "empeorando": "🔴"}.get(trend, "⚪")
        st.info(f"{icon} Tendencia: **{trend}**")

        st.subheader("🔁 Patrones de error comunes")
        patrones = anomalias.get("patrones_fallo", {})
        if patrones:
            st.dataframe([{"Error": k, "Frecuencia": v} for k, v in patrones.items()], use_container_width=True, hide_index=True)
        else:
            st.info("No hay patrones de error registrados.")

        st.subheader("⚙️ Recomendaciones de optimización")
        try:
            recoms = monitor.recomendar_optimizaciones()
            if recoms:
                for r in recoms:
                    prioridad = r.get("prioridad", "baja")
                    badge = {"alta": "🔴 ALTA", "media": "🟡 MEDIA", "baja": "🟢 BAJA"}.get(prioridad, "⚪")
                    with st.expander(f"{badge} — {r.get('area','')}: {r.get('problema','')[:60]}"):
                        st.markdown(f"**Problema:** {r.get('problema','')}")
                        st.markdown(f"**Recomendación:** {r.get('recomendacion','')}")
                        st.markdown(f"**Impacto esperado:** {r.get('impacto_esperado','')}")
            else:
                st.info("No hay recomendaciones.")
        except Exception:
            st.info("No hay recomendaciones.")

# ═══════════════════════════════════════════════
# TAB: Alertas Automáticas
# ═══════════════════════════════════════════════

with tab_alertas:
    try:
        alertas = monitor.verificar_alertas()
    except Exception:
        alertas = []

    if not alertas:
        st.success("✅ Sin alertas activas. El sistema opera dentro de parámetros normales.")
    else:
        st.subheader(f"🚨 {len(alertas)} alerta(s) activa(s)")
        for a in alertas:
            sev = a.get("severidad", "baja")
            icon = {"alta": "🔴", "media": "🟡", "baja": "🟢"}.get(sev, "⚪")
            with st.expander(f"{icon} [{sev.upper()}] {a.get('tipo', 'desconocido')} — {a.get('fecha', '?')}"):
                st.markdown(f"**{a.get('mensaje', '')}**")
                if a.get("consulta_id"):
                    st.caption(f"Consulta ID: {a['consulta_id']}")
                st.caption(f"Severidad: {sev}")

        st.markdown("---")
        st.caption("Las alertas se generan automáticamente según umbrales configurados en config.py")
