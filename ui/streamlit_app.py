import streamlit as st
from pathlib import Path
import yaml, json

st.set_page_config(page_title="LexDomus–PI MVP", layout="wide")
st.title("LexDomus–PI — MVP (RAGA+MCP, sin LLM)")

with st.sidebar:
    st.header("Proyecto")
    st.write("Asistente deliberativo para DPI (cesión/licencia)")
    st.divider()
    policy_path = Path(__file__).resolve().parents[1] / "policies" / "policy.yaml"
    if policy_path.exists():
        st.code(policy_path.read_text(), language="yaml")

tab1, tab2, tab3 = st.tabs(["1) Inquiry Graph", "2) Citas & Comparativa", "3) Cláusula + EEE + A2J"])

# Estado simple en sesión
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "last_input" not in st.session_state:
    st.session_state["last_input"] = {"clause": "", "juris": "ES"}

with tab1:
    st.subheader("Entrada")
    clause = st.text_area("Pega aquí la cláusula a analizar", height=220, value=st.session_state["last_input"]["clause"])
    juris = st.selectbox("Jurisdicción objetivo", ["ES","EU","US","INT"], index=["ES","EU","US","INT"].index(st.session_state["last_input"]["juris"]))
    if st.button("Analizar"):
        from app.pipeline import analyze_clause
        res = analyze_clause(clause, juris)
        st.session_state["last_result"] = res
        st.session_state["last_input"] = {"clause": clause, "juris": juris}
        st.success("Análisis completado. Revisa las pestañas 2 y 3.")

    st.caption("Nota: esta demo funciona sin LLM; usa RAG+heurísticas para EEE/flags.")

with tab2:
    st.subheader("Evidencias (por nodo)")
    res = st.session_state["last_result"]
    if not res:
        st.info("Ejecuta el análisis en la pestaña 1.")
    else:
        for i, item in enumerate(res["per_node"], start=1):
            col1, col2 = st.columns([1,3])
            with col1:
                st.markdown(f"**Nodo {i}**")
                st.json(item["node"])
            with col2:
                retr = item["retrieval"]
                if retr["status"] == "OK":
                    st.write("Citas:")
                    for c in retr["citations"]:
                        meta = c["meta"]
                        st.markdown(f"- **{meta.get('title','')}** · `{meta.get('source','')}` · `{meta.get('jurisdiction','')}` · pin:{meta.get('pinpoint',False)}")
                        st.code(c["text"][:600])
                else:
                    st.warning("No concluyente: falta evidencia con pinpoint")

with tab3:
    st.subheader("Dictamen (demo)")
    res = st.session_state["last_result"]
    if not res:
        st.info("Ejecuta el análisis en la pestaña 1.")
    else:
        eee = res["EEE"]
        st.markdown("### EEE")
        st.write(eee)
        st.markdown("### Flags")
        st.write(res["flags"] or "—")
        st.markdown("### Cláusula alternativa (base)")
        st.code(res["alternative_clause"])
        st.markdown("### Resumen A2J (plantilla)")
        a2j = Path(__file__).resolve().parents[1] / "templates" / "RESUMEN_A2J.md"
        st.write(a2j.read_text() if a2j.exists() else "—")
