# --- Bootstrap de paths para que Streamlit (carpeta ui/) encuentre el paquete app/ ---
from pathlib import Path
import sys, os, json

ROOT = Path(__file__).resolve().parents[1]  # raíz del repo
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYTHONPATH", str(ROOT))

import streamlit as st

# Intenta cargar OPENAI_API_KEY desde Secrets (Streamlit Cloud) y propágalo al entorno
try:
    if "OPENAI_API_KEY" in st.secrets and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

from app.pipeline import analyze_clause

st.set_page_config(page_title="LexDomus–PI MVP", layout="wide")
st.title("LexDomus–PI — MVP (RAGA+MCP)")

with st.sidebar:
    st.header("Proyecto")
    policy_path = ROOT / "policies" / "policy.yaml"
    if policy_path.exists():
        st.code(policy_path.read_text(), language="yaml")
    st.divider()

    # Estado de reformas
    report_path = ROOT / "data" / "status" / "reforms_report.json"
    if report_path.exists():
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

    # Motor de redacción con guardas por clave
    has_openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    options = ["MOCK (sin LLM)"] + (["LLM (OpenAI)"] if has_openai else [])
    engine = st.radio("Motor de redacción", options, index=0)

    # Si no hay clave, fuerza MOCK y avisa; si hay, respeta la elección
    if engine.startswith("LLM") and not has_openai:
        st.warning("No hay OPENAI_API_KEY configurada en esta app. Usaré el motor MOCK.")
        os.environ["USE_LLM"] = "0"
    else:
        os.environ["USE_LLM"] = "1" if engine.startswith("LLM") else "0"

tab1, tab2, tab3, tab4 = st.tabs(
    ["1) Inquiry Graph", "2) Citas & Comparativa", "3) Dictamen & A2J", "4) Tendencia del corpus"]
)

if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "last_input" not in st.session_state:
    st.session_state["last_input"] = {"clause": "", "juris": "ES"}

with tab1:
    st.subheader("Entrada")
    clause = st.text_area(
        "Pega aquí la cláusula a analizar",
        height=220,
        value=st.session_state["last_input"]["clause"],
    )
    juris = st.selectbox(
        "Jurisdicción objetivo",
        ["ES", "EU", "US", "INT"],
        index=["ES", "EU", "US", "INT"].index(st.session_state["last_input"]["juris"]),
    )
    if st.button("Analizar"):
        try:
            res = analyze_clause(clause, juris)
            st.session_state["last_result"] = res
            st.session_state["last_input"] = {"clause": clause, "juris": juris}
            st.success(f"Análisis completado con motor {res.get('engine')} · Gate={res['gate']['status']}")
        except Exception as e:
            st.error(f"Error al analizar: {type(e).__name__}: {e}")
    st.caption("La demo usa RAG+heurísticas/LLM con disciplina 'source-required'.")

with tab2:
    st.subheader("Evidencias (por nodo)")
    res = st.session_state["last_result"]
    if not res:
        st.info("Ejecuta el análisis en la pestaña 1.")
    else:
        for i, item in enumerate(res["per_node"], start=1):
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**Nodo {i}**")
                st.json(item["node"])
            with col2:
                retr = item["retrieval"]
                if retr["status"] == "OK":
                    st.write("Citas:")
                    for c in retr["citations"]:
                        meta = c["meta"]
                        ref = meta.get("ref_label", "")
                        url = meta.get("ref_url", "")
                        pin = "✅" if meta.get("pinpoint", False) else "—"
                        ls, le = meta.get("line_start"), meta.get("line_end")
                        head = (
                            f"**{meta.get('title','')}** · "
                            f"`{meta.get('source','')}` · "
                            f"`{meta.get('jurisdiction','')}` · pin:{pin}"
                        )
                        st.markdown(head)
                        if ref:
                            if url:
                                st.markdown(f"Ref: [{ref}]({url}) · líneas {ls}–{le}")
                            else:
                                st.markdown(f"Ref: {ref} · líneas {ls}–{le}")
                        st.code(c["text"][:800])
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
        a2j = ROOT / "templates" / "RESUMEN_A2J.md"
        st.write(a2j.read_text() if a2j.exists() else "—")

with tab4:
    st.subheader("Histórico de familias (chunks)")

    # Helpers seguros para CSVs
    @st.cache_data(show_spinner=False)
    def _read_csv_safe(path: Path):
        try:
            import pandas as pd  # lazy import
        except Exception as e:
            return None, f"ImportError de pandas: {e}"
        if not path.exists():
            return None, f"No existe el archivo: {path}"
        try:
            df = pd.read_csv(path)
            return df, None
        except Exception as e:
            return None, f"Error leyendo CSV {path.name}: {e}"

    hist = ROOT / "data" / "status" / "families_history.csv"
    delt = ROOT / "data" / "status" / "families_deltas.csv"

    df, err = _read_csv_safe(hist)
    if err:
        st.info(err + ". Ejecuta un rebuild para generar los CSV.")
    else:
        import pandas as pd  # ya debería existir si _read_csv_safe pasó
        if df.empty:
            st.info("Histórico vacío.")
        else:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
            if "total" in df.columns:
                df["total"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
            families = [c for c in df.columns if c not in ("timestamp", "total")]
            for fam in families:
                df[fam] = pd.to_numeric(df[fam], errors="coerce").fillna(0)

            st.markdown("**Total de chunks**")
            st.line_chart(df.set_index("timestamp")["total"])
            if families:
                st.markdown("**Chunks por familia**")
                st.line_chart(df.set_index("timestamp")[families])

    st.divider()
    st.subheader("Deltas por rebuild")

    df2, err2 = _read_csv_safe(delt)
    if err2:
        st.info(err2 + ". Se generará en el próximo rebuild.")
    else:
        import pandas as pd
        if df2.empty:
            st.info("Sin deltas todavía.")
        else:
            df2["timestamp"] = pd.to_datetime(df2["timestamp"], errors="coerce")
            df2 = df2.dropna(subset=["timestamp"]).sort_values("timestamp")
            if "total" in df2.columns:
                df2["total"] = pd.to_numeric(df2["total"], errors="coerce").fillna(0)
            fam2 = [c for c in df2.columns if c not in ("timestamp", "total")]
            for fam in fam2:
                df2[fam] = pd.to_numeric(df2[fam], errors="coerce").fillna(0)

            st.markdown("**Delta total**")
            st.line_chart(df2.set_index("timestamp")["total"])
            if fam2:
                st.markdown("**Delta por familia**")
                st.line_chart(df2.set_index("timestamp")[fam2])


