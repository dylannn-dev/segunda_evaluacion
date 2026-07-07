"""
app.py
------
Interfaz Streamlit de CrediRapido. Responsabilidad unica: capturar la
solicitud, encolarla en Redis (via queue_client.encolar_solicitud) y
mostrar el avance en vivo consultando el estado publicado por el Worker.

La interfaz NUNCA ejecuta el scoring directamente: solo encola y consulta
estado. Esto es lo que se pide justificar en el Ejercicio 1 / Ejercicio 3
(desacoplamiento interfaz-procesamiento).
"""

import time
import streamlit as st
from queue_client import encolar_solicitud, leer_estado, largo_cola

st.set_page_config(page_title="CrediRapido - Scoring de Solicitudes", page_icon="\U0001F4B3")
st.title("CrediRapido — Motor de Scoring Crediticio (asincrono)")
st.caption("La interfaz solo encola la solicitud. El calculo lo hace un Worker en segundo plano.")

with st.form("solicitud_form"):
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre del solicitante", "Juan Perez")
        monto = st.number_input("Monto solicitado (CLP)", min_value=0, value=2_000_000, step=100_000)
        ingreso = st.number_input("Ingreso mensual (CLP)", min_value=0, value=900_000, step=50_000)
        deuda = st.number_input("Deuda mensual actual (CLP)", min_value=0, value=150_000, step=10_000)
    with col2:
        antiguedad = st.number_input("Antiguedad laboral (meses)", min_value=0, value=24, step=1)
        edad = st.number_input("Edad", min_value=0, value=32, step=1)
        historial = st.selectbox("Historial crediticio", ["bueno", "regular", "malo"])
        region = st.text_input("Region", "Metropolitana")

    submitted = st.form_submit_button("Enviar solicitud")

if submitted:
    payload = {
        "nombre_solicitante": nombre, "monto_solicitado": monto,
        "ingreso_mensual": ingreso, "deuda_mensual_actual": deuda,
        "antiguedad_laboral_meses": antiguedad, "edad": edad,
        "historial_crediticio": historial, "region": region,
    }
    task_id = encolar_solicitud(payload)
    st.session_state["ultimo_task_id"] = task_id
    st.success(f"Solicitud encolada. task_id = {task_id}")

st.divider()
st.subheader("Seguimiento de solicitud")

task_id_input = st.text_input("task_id a consultar", st.session_state.get("ultimo_task_id", ""))
auto_refresh = st.checkbox("Auto-actualizar cada 1.5s", value=True)

if task_id_input:
    estado = leer_estado(task_id_input)
    if estado is None:
        st.warning("No se encontro estado para ese task_id (puede haber expirado o no existir).")
    else:
        st.progress(min(int(estado["avance_pct"]), 100) / 100)
        st.write(f"**Estado:** `{estado['estado']}`  |  **Avance:** {estado['avance_pct']}%")
        st.write(f"**Mensaje:** {estado['mensaje']}")
        st.write(f"**Ultima actualizacion:** {estado['timestamp']}")
        if estado.get("resultado"):
            st.json(estado["resultado"])
        if auto_refresh and estado["estado"] not in ("completado", "fallido"):
            time.sleep(1.5)
            st.rerun()

st.divider()
st.caption(f"Tareas actualmente en cola: {largo_cola()}")
