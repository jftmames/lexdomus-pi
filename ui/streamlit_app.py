import streamlit as st
import json, os, yaml
from pathlib import Path

st.set_page_config(page_title="LexDomus–PI MVP", layout="wide")
st.title("LexDomus–PI — MVP (RAGA+MCP)")

with st.sidebar:
    st.header("Proyecto")
    st.write("Asistente deliberativo para DPI (cesión/licencia)")
    st.divider()
    policy_path = Path(__file__).resolve().parents[1] / "policies" / "policy.yaml"
    if policy_path.exists():
        st.code(policy_path.read_text(), language="yaml")

tab1, tab2, tab3 = st.tabs(["1) Inquiry Graph", "2) Citas & Comparativa", "3) Cláusula + EEE + A2J"])

with tab1:
    st.subheader("Entrada")
    clause = st.text_area("Pega aquí la cláusula a analizar", height=200)
    juris = st.selectbox("Jurisdicción objetivo", ["ES","EU","US","INT"])
    if st.button("Descomponer"):
        st.info("Aquí se llamaría a verdiktia.inquiry_engine (planner) → JSON de nodos.")

with tab2:
    st.subheader("Evidencias")
    st.write("Aquí se mostrarán los pasajes recuperados (lex_domus.retriever + rag_pipeline) con citas pinpoint y conflictos.")

with tab3:
    st.subheader("Dictamen")
    st.write("Se renderiza el Análisis, Pros/Contras, Contraargumentos, Cláusula alternativa y EEE + flags.")
    st.caption("Si no hay evidencia suficiente: salida 'No concluyente + qué falta'.")
