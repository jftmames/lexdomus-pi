import streamlit as st
from pathlib import Path
import os

st.set_page_config(page_title="LexDomus–PI MVP", layout="wide")
st.title("LexDomus–PI — MVP (RAGA+MCP)")

with st.sidebar:
    st.header("Proyecto")
    policy_path = Path(__file__).resolve().parents[1] / "policies" / "policy.yaml"
    if policy_path.exists():
        st.code(policy_path.read_text(), language="yaml")
    st.divider()

    # Estado de reformas
    report_path = Path(__file__).resolve().parents[1] / "data" / "status" / "reforms_report.json"
    if report_path.exists():
        import json
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        changed = rep.get("changed_count", 0)
        if changed > 0:
            st.error(f"Corpus: {changed} documento(s) con cambios pendientes de revisión.")
            with st.expander("Ver detalle"):
                st.json(rep)
        else:
            st.success("Corpus al día (sin cambios detectados).")
    else:
        st.info("Sin reporte de reformas aún.")

    st.divider()
    engine = st.radio("Motor de redacción", ["MOCK (sin LLM)", "LLM (OpenAI)"], index=0)
    os.environ["USE_LLM"] = "1" if engine.startswith("LLM") else "0"


tab1, tab2, tab3 = st.tabs(["1) Inquiry Graph", "2) Citas & Comparativa", "3) Dictamen & A2J"])

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
        st.success(f"Análisis completado con motor {res.get('engine')} · Gate={res['gate']['status']}")
    st.caption("La demo usa RAG+heurísticas/LLM con disciplina 'source-required'.")

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
                        ref = meta.get("ref_label","")
                        url = meta.get("ref_url","")
                        pin = "✅" if meta.get("pinpoint", False) else "—"
                        ls, le = meta.get("line_start"), meta.get("line_end")
                        head = f"**{meta.get('title','')}** · `{meta.get('source','')}` · `{meta.get('jurisdiction','')}` · pin:{pin}"
                        st.markdown(head)
                        if ref:
                            if url:
                                st.markdown(f"Ref: [{ref}]({url}) · líneas {ls}–{le}")
                            else:
                                st.markdown(f"Ref: {ref} · líneas {ls}–{le}")
                        st.code(c['text'][:800])
                else:
                    st.warning("No concluyente: falta evidencia con pinpoint")

with tab3:
    st.subheader("Dictamen & A2J")
    res = st.session_state["last_result"]
    if not res:
        st.info("Ejecuta el análisis en la pestaña 1.")
    else:
        st.markdown("### Gate")
        st.json(res["gate"])
        st.markdown("### EEE")
        st.write(res["EEE"])
        st.markdown("### Flags")
        st.write(res["flags"] or "—")

        st.markdown("### Análisis")
        st.markdown(res["opinion"]["analysis_md"])

        colA, colB = st.columns(2)
        with colA:
            st.markdown("### Pros")
            st.write(res["opinion"]["pros"] or "—")
        with colB:
            st.markdown("### Contras")
            st.write(res["opinion"]["cons"] or "—")

        st.markdown("### Lectura alternativa (Devil’s Advocate)")
        st.json(res["opinion"]["devils_advocate"])

        st.markdown("### Cláusula alternativa (base)")
        st.code(res["alternative_clause"])

        st.markdown("### Resumen A2J (plantilla)")
        a2j = Path(__file__).resolve().parents[1] / "templates" / "RESUMEN_A2J.md"
        st.write(a2j.read_text() if a2j.exists() else "—")

