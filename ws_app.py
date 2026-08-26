"""
ws_app.py
WS Display — CallasFlow
Streamlit app with profile runner and visual profile builder.

Run with:
    python -m streamlit run ws_app.py
"""

import streamlit as st
import tempfile, os, sys, json, importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ws_pdf_tools as ws
importlib.reload(ws)

PROFILES_DIR = Path(__file__).parent / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="CallasFlow", page_icon="📄", layout="wide")

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0f1623; }
    .main .block-container { background-color: #0f1623; padding-top: 1.2rem; }
    section[data-testid="stSidebar"] { background-color: #131d2e; border-right: 1px solid rgba(255,255,255,0.08); }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

    h1, h2, h3, h4, p, label, div { color: #e2e8f0; }
    .stMarkdown p { color: #b0bec5; }

    .stButton>button {
        background-color: #3b82f6; color: white; border: none;
        border-radius: 6px; padding: 0.5rem 1.5rem;
        font-weight: 600; letter-spacing: 0.02em;
        box-shadow: 0 0 12px rgba(59,130,246,0.35);
        transition: all 0.15s ease;
    }
    .stButton>button:hover { background-color: #60a5fa; box-shadow: 0 0 18px rgba(59,130,246,0.55); }

    .stSelectbox>div>div, .stNumberInput>div>div>input, .stTextInput>div>div>input,
    .stTextArea textarea {
        background-color: #1e2a3e !important; color: #e2e8f0 !important;
        border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 6px !important;
    }
    [data-baseweb="popover"] { background-color: #1e2a3e !important; }
    [data-baseweb="menu"] { background-color: #1e2a3e !important; }
    [data-baseweb="menu"] li { background-color: #1e2a3e !important; color: #e2e8f0 !important; }
    [data-baseweb="menu"] li:hover { background-color: #2d3f5e !important; color: #fff !important; }
    [data-baseweb="select"] div, [data-baseweb="select"] span { color: #e2e8f0 !important; }
    [role="listbox"] { background-color: #1e2a3e !important; }
    [role="option"] { background-color: #1e2a3e !important; color: #e2e8f0 !important; }
    [role="option"]:hover { background-color: #2d3f5e !important; color: #fff !important; }

    .stApp::before {
        content: ''; display: block; height: 3px;
        background: linear-gradient(90deg, #3b82f6, #60a5fa, #2563eb);
        position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
    }

    .stFileUploader { background-color: #1a2540; border: 1px dashed rgba(59,130,246,0.4); border-radius: 8px; padding: 0.5rem; }
    .stFileUploader label { color: #7f9bb5 !important; }
    [data-testid="stFileUploaderDropzone"] { background-color: #1a2540 !important; border: none !important; }
    [data-testid="stFileUploaderDropzone"] button { background-color: #3b82f6 !important; color: white !important; border: none !important; border-radius: 6px !important; }

    .streamlit-expanderHeader { background-color: #1a2540 !important; color: #e2e8f0 !important; border-radius: 6px; }
    .streamlit-expanderContent { background-color: #161f31 !important; border: 1px solid rgba(255,255,255,0.06); border-radius: 0 0 6px 6px; }

    hr { border-color: rgba(255,255,255,0.08) !important; }
    .stCaption, footer { color: #4a6080 !important; }
    .stSpinner > div { border-top-color: #3b82f6 !important; }

    [data-testid="metric-container"] {
        background-color: #1a2540; border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px; padding: 0.75rem 1rem;
    }
    [data-testid="metric-container"] label { color: #7f9bb5 !important; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { color: #fff !important; font-size: 1.6rem !important; font-weight: 700; }

    .result-box  { background: rgba(34,197,94,0.1);  border-left: 4px solid #22c55e; padding: 1rem; border-radius: 4px; margin: 0.5rem 0; color: #e2e8f0; }
    .issue-box   { background: rgba(239,68,68,0.1);  border-left: 4px solid #ef4444; padding: 1rem; border-radius: 4px; margin: 0.5rem 0; color: #e2e8f0; }
    .warn-box    { background: rgba(234,179,8,0.1);  border-left: 4px solid #eab308; padding: 1rem; border-radius: 4px; margin: 0.5rem 0; color: #e2e8f0; }
    .info-box    { background: rgba(37,99,235,0.1);  border-left: 4px solid #2563eb; padding: 1rem; border-radius: 4px; margin: 0.5rem 0; color: #e2e8f0; }

    /* Step cards in builder */
    .step-card {
        background: #1a2540; border: 1px solid rgba(59,130,246,0.2);
        border-radius: 8px; padding: 0.75rem 1rem; margin: 0.4rem 0;
    }
    .step-num { color: #3b82f6; font-weight: 700; font-size: 0.85rem; }
    .step-label { color: #e2e8f0; font-weight: 600; font-size: 0.9rem; }
    .step-params { color: #7f9bb5; font-size: 0.78rem; margin-top: 2px; }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] { background-color: #131d2e !important; border-radius: 8px; padding: 4px; gap: 4px; }
    .stTabs [data-baseweb="tab"] { background-color: transparent !important; color: #7f9bb5 !important; border-radius: 6px; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #1e2a3e !important; color: #e2e8f0 !important; }
    .stTabs [data-baseweb="tab-panel"] { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex; align-items:center; gap:1.2rem; padding:0.5rem 0 1.2rem 0;
            border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:1.5rem;">
    <div style="background:linear-gradient(135deg,#1d4ed8,#3b82f6); width:64px; height:64px; border-radius:12px;
                display:flex; align-items:center; justify-content:center; font-size:1.4rem; font-weight:900;
                color:white; letter-spacing:-0.03em; flex-shrink:0;
                box-shadow:0 0 28px rgba(59,130,246,0.5), 0 4px 12px rgba(0,0,0,0.4);">CF</div>
    <div>
        <div style="font-size:1.6rem; font-weight:800; color:#fff; letter-spacing:-0.02em; line-height:1.1;">CallasFlow</div>
        <div style="font-size:0.7rem; color:#3b82f6; letter-spacing:0.12em; text-transform:uppercase; font-weight:600; margin-top:2px;">
            WS Display &nbsp;·&nbsp; PDF Finishing &nbsp;·&nbsp; Profile Builder
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_all_profiles():
    """Return dict of {display_name: (path, profile_dict)} from profiles/ folder."""
    profiles = {}
    for p in sorted(PROFILES_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            profiles[data.get("name", p.stem)] = (p, data)
        except Exception:
            pass
    return profiles


def save_profile_to_disk(profile: dict):
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in profile["name"])
    safe_name = safe_name.strip().replace(" ", "_").lower()
    path = PROFILES_DIR / f"{safe_name}.json"
    path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    return path


def params_summary(step: dict) -> str:
    p = step.get("params", {})
    if not p:
        return ""
    return "  ·  " + ",  ".join(f"{k}: {v}" for k, v in p.items())


def page_info_expander(input_path: str):
    import fitz
    with st.expander("📐 Page Info", expanded=True):
        doc = fitz.open(input_path)
        cols = st.columns(min(len(doc), 5))
        for i, page in enumerate(doc):
            if i >= 5:
                st.caption(f"… and {len(doc)-5} more pages")
                break
            mb, tb = page.mediabox, page.trimbox
            with cols[i]:
                st.metric(f"Page {i+1}",
                          f"{mb.width/72:.2f}\" × {mb.height/72:.2f}\"",
                          delta=f"TrimBox: {tb.width/72:.2f}\" × {tb.height/72:.2f}\"" if tb != mb else "No TrimBox",
                          delta_color="off")
        doc.close()


def success_banner(operation: str):
    st.markdown(f"""
    <div style="background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3);
                border-radius:10px; padding:1rem 1.25rem; margin:1rem 0;
                display:flex; align-items:center; gap:0.75rem;">
        <div style="font-size:1.5rem;">✅</div>
        <div>
            <div style="color:#22c55e; font-weight:700; font-size:0.95rem;">Processing Complete</div>
            <div style="color:#7f9bb5; font-size:0.8rem; margin-top:2px;">{operation}</div>
        </div>
    </div>""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:0.6rem 0 1rem 0; border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:1rem;">
        <div style="font-size:0.65rem; color:#3b82f6; letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">PDF AUTOMATION SUITE</div>
        <div style="font-size:0.62rem; color:#4a6080; margin-top:2px;">v2.0 &nbsp;·&nbsp; WS Display</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Poppler path**")
    poppler_path = st.text_input("Poppler bin folder", value=ws.POPPLER_BIN,
                                  help="Path to Poppler bin containing pdftocairo.exe",
                                  label_visibility="collapsed")
    ws.POPPLER_BIN = poppler_path


# ── Main Tabs ──────────────────────────────────────────────────────────────────
tab_run, tab_build, tab_preflight = st.tabs(["▶  Run Profile", "🔧  Build Profile", "📋  Preflight Check"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RUN PROFILE
# ══════════════════════════════════════════════════════════════════════════════
with tab_run:
    all_profiles = load_all_profiles()

    if not all_profiles:
        st.info("No profiles found in the profiles/ folder. Use the **Build Profile** tab to create one.")
    else:
        left, right = st.columns([1, 2])

        with left:
            st.markdown('<div style="font-size:0.75rem; color:#7f9bb5; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:0.4rem;">Select Profile</div>', unsafe_allow_html=True)
            profile_name = st.selectbox("Profile", list(all_profiles.keys()), label_visibility="collapsed")
            _, profile_data = all_profiles[profile_name]

            # Description card
            desc = profile_data.get("description", "")
            cat  = profile_data.get("category", "")
            if desc:
                st.markdown(f"""
                <div style="background:rgba(59,130,246,0.08); border:1px solid rgba(59,130,246,0.2);
                            border-radius:8px; padding:0.75rem; margin:0.5rem 0 0.75rem 0;
                            font-size:0.8rem; color:#93b4d4; line-height:1.5;">
                    {"<span style='font-size:0.65rem; color:#3b82f6; text-transform:uppercase; font-weight:700; letter-spacing:0.08em;'>" + cat + "</span><br>" if cat else ""}
                    {desc}
                </div>""", unsafe_allow_html=True)

            # Step summary
            steps = profile_data.get("steps", [])
            st.markdown(f'<div style="font-size:0.7rem; color:#7f9bb5; margin-bottom:0.3rem;">{len(steps)} step{"s" if len(steps)!=1 else ""}</div>', unsafe_allow_html=True)
            for i, s in enumerate(steps):
                op_meta = ws.AVAILABLE_OPS.get(s["op"], {})
                label = op_meta.get("label", s["op"])
                params_str = params_summary(s)
                st.markdown(f"""
                <div class="step-card">
                    <span class="step-num">{i+1}.</span>&nbsp;
                    <span class="step-label">{label}</span>
                    <div class="step-params">{params_str}</div>
                </div>""", unsafe_allow_html=True)

        with right:
            st.markdown('<div style="font-size:0.75rem; color:#7f9bb5; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:0.5rem;">Upload PDF</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("Drop your PDF here", type=["pdf"], label_visibility="collapsed")

            if uploaded:
                st.markdown(f"**File:** `{uploaded.name}`  |  **Size:** {uploaded.size/1024:.1f} KB")

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(uploaded.read())
                    input_path = tmp.name

                page_info_expander(input_path)
                st.divider()

                if st.button(f"▶  Run: {profile_name}", use_container_width=True):
                    output_path = tempfile.mktemp(suffix=".pdf")
                    with st.spinner(f"Running {profile_name}…"):
                        try:
                            ws.run_profile(input_path, output_path, profile_data)
                            if os.path.exists(output_path):
                                success_banner(f"{profile_name} applied successfully")
                                stem = Path(uploaded.name).stem
                                out_name = f"{stem}_finished.pdf"
                                with open(output_path, "rb") as f:
                                    st.download_button("⬇  Download Result", f.read(),
                                                       file_name=out_name, mime="application/pdf",
                                                       use_container_width=True)
                        except Exception as e:
                            st.error(f"❌ Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BUILD PROFILE
# ══════════════════════════════════════════════════════════════════════════════
with tab_build:

    # ── Session state ──────────────────────────────────────────────────────────
    if "builder_steps" not in st.session_state:
        st.session_state.builder_steps = []
    if "builder_name" not in st.session_state:
        st.session_state.builder_name = "New Profile"
    if "builder_desc" not in st.session_state:
        st.session_state.builder_desc = ""
    if "builder_cat" not in st.session_state:
        st.session_state.builder_cat = "Finishing"
    if "load_into_builder" not in st.session_state:
        st.session_state.load_into_builder = None

    # ── Load existing profile into builder ─────────────────────────────────────
    all_profiles_b = load_all_profiles()
    col_load, col_new = st.columns([3, 1])
    with col_load:
        load_choice = st.selectbox("Load existing profile to edit",
                                   ["— start fresh —"] + list(all_profiles_b.keys()),
                                   label_visibility="collapsed")
    with col_new:
        if st.button("Load →", use_container_width=True) and load_choice != "— start fresh —":
            _, pdata = all_profiles_b[load_choice]
            st.session_state.builder_name = pdata.get("name", "")
            st.session_state.builder_desc = pdata.get("description", "")
            st.session_state.builder_cat  = pdata.get("category", "Finishing")
            st.session_state.builder_steps = [dict(s) for s in pdata.get("steps", [])]
            st.rerun()

    st.divider()
    left_b, right_b = st.columns([1, 2])

    # ── Left: profile meta + add step ─────────────────────────────────────────
    with left_b:
        st.markdown("#### Profile Details")
        st.session_state.builder_name = st.text_input("Profile Name", value=st.session_state.builder_name)
        st.session_state.builder_desc = st.text_area("Description", value=st.session_state.builder_desc, height=80)
        st.session_state.builder_cat  = st.selectbox("Category",
            ["Finishing", "Preparation", "Imposition", "Proofing", "Other"],
            index=["Finishing","Preparation","Imposition","Proofing","Other"].index(
                st.session_state.builder_cat) if st.session_state.builder_cat in
                ["Finishing","Preparation","Imposition","Proofing","Other"] else 0)

        st.divider()
        st.markdown("#### Add Step")

        # Group ops by category for the selector
        all_op_ids   = list(ws.AVAILABLE_OPS.keys())
        all_op_labels = [ws.AVAILABLE_OPS[o]["label"] for o in all_op_ids]
        cat_options  = [f"[{ws.AVAILABLE_OPS[o]['category']}]  {ws.AVAILABLE_OPS[o]['label']}" for o in all_op_ids]

        selected_idx = st.selectbox("Operation", range(len(all_op_ids)),
                                    format_func=lambda i: cat_options[i],
                                    label_visibility="collapsed")
        selected_op_id   = all_op_ids[selected_idx]
        selected_op_meta = ws.AVAILABLE_OPS[selected_op_id]

        # Show op description
        st.markdown(f'<div style="font-size:0.78rem; color:#7f9bb5; margin:0.3rem 0 0.6rem 0;">{selected_op_meta["description"]}</div>', unsafe_allow_html=True)

        # Dynamic param inputs
        new_params = {}
        for param in selected_op_meta.get("params", []):
            pname  = param["name"]
            plabel = param["label"]
            ptype  = param["type"]
            if ptype == "float":
                new_params[pname] = st.number_input(plabel, value=float(param["default"]),
                                                     step=float(param.get("step", 0.25)),
                                                     key=f"p_{selected_op_id}_{pname}")
            elif ptype == "int":
                new_params[pname] = st.number_input(plabel, value=int(param["default"]),
                                                     min_value=param.get("min", 1),
                                                     max_value=param.get("max", 100),
                                                     step=1,
                                                     key=f"p_{selected_op_id}_{pname}")
            elif ptype == "select":
                opts = param["options"]
                def_idx = opts.index(param["default"]) if param["default"] in opts else 0
                new_params[pname] = st.selectbox(plabel, opts, index=def_idx,
                                                  key=f"p_{selected_op_id}_{pname}")

        if st.button("＋  Add Step", use_container_width=True):
            step_def = {"op": selected_op_id}
            if new_params:
                step_def["params"] = new_params
            st.session_state.builder_steps.append(step_def)
            st.rerun()

    # ── Right: step list + controls + save ─────────────────────────────────────
    with right_b:
        steps_b = st.session_state.builder_steps
        n = len(steps_b)

        st.markdown(f"#### Step Sequence  <span style='font-size:0.75rem; color:#7f9bb5;'>({n} step{'s' if n!=1 else ''})</span>", unsafe_allow_html=True)

        if not steps_b:
            st.markdown('<div class="info-box" style="text-align:center; padding:2rem;">← Add steps from the left panel to build your profile.</div>', unsafe_allow_html=True)
        else:
            for i, step in enumerate(steps_b):
                op_meta = ws.AVAILABLE_OPS.get(step["op"], {})
                label   = op_meta.get("label", step["op"])
                pstr    = params_summary(step)
                ffeat   = op_meta.get("ffeat", "")

                col_card, col_up, col_dn, col_del = st.columns([10, 1, 1, 1])
                with col_card:
                    st.markdown(f"""
                    <div class="step-card">
                        <span class="step-num">{i+1}.</span>&nbsp;
                        <span class="step-label">{label}</span>
                        {"<span style='font-size:0.65rem; color:#3b82f6; margin-left:8px;'>ffeat: " + ffeat + "</span>" if ffeat else ""}
                        <div class="step-params">{pstr}</div>
                    </div>""", unsafe_allow_html=True)
                with col_up:
                    if i > 0 and st.button("↑", key=f"up_{i}", help="Move up"):
                        steps_b[i-1], steps_b[i] = steps_b[i], steps_b[i-1]
                        st.rerun()
                with col_dn:
                    if i < n-1 and st.button("↓", key=f"dn_{i}", help="Move down"):
                        steps_b[i], steps_b[i+1] = steps_b[i+1], steps_b[i]
                        st.rerun()
                with col_del:
                    if st.button("✕", key=f"del_{i}", help="Remove step"):
                        steps_b.pop(i)
                        st.rerun()

        st.divider()

        # Save + test
        save_col, clear_col = st.columns([3, 1])
        with save_col:
            if st.button("💾  Save Profile", use_container_width=True, disabled=not steps_b):
                if not st.session_state.builder_name.strip():
                    st.error("Give the profile a name first.")
                else:
                    profile_to_save = {
                        "name":        st.session_state.builder_name.strip(),
                        "description": st.session_state.builder_desc.strip(),
                        "category":    st.session_state.builder_cat,
                        "steps":       steps_b,
                    }
                    saved_path = save_profile_to_disk(profile_to_save)
                    st.success(f"Saved → {saved_path.name}")
        with clear_col:
            if st.button("🗑  Clear", use_container_width=True):
                st.session_state.builder_steps = []
                st.session_state.builder_name  = "New Profile"
                st.session_state.builder_desc  = ""
                st.rerun()

        # Test run
        if steps_b:
            st.divider()
            st.markdown("#### Test Run")
            test_upload = st.file_uploader("Upload a PDF to test this profile",
                                           type=["pdf"], key="builder_test_upload")
            if test_upload:
                if st.button("▶  Test Profile", use_container_width=True):
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
                        tmp_in.write(test_upload.read())
                        t_input = tmp_in.name
                    t_output = tempfile.mktemp(suffix=".pdf")
                    test_profile = {
                        "name":  st.session_state.builder_name,
                        "steps": steps_b,
                    }
                    with st.spinner("Testing profile…"):
                        try:
                            ws.run_profile(t_input, t_output, test_profile)
                            if os.path.exists(t_output):
                                success_banner("Test run complete")
                                stem = Path(test_upload.name).stem
                                with open(t_output, "rb") as f:
                                    st.download_button("⬇  Download Test Result", f.read(),
                                                       file_name=f"{stem}_test.pdf",
                                                       mime="application/pdf",
                                                       use_container_width=True)
                        except Exception as e:
                            st.error(f"❌ {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PREFLIGHT CHECK
# ══════════════════════════════════════════════════════════════════════════════
with tab_preflight:
    pf_col1, pf_col2 = st.columns([1, 2])

    with pf_col1:
        st.markdown("#### Options")
        black_target = st.selectbox("Black ink target", ["100k", "75x3"],
                                    help="100k = pure black (0,0,0,100). 75x3 = rich black (75,75,75,100).")
        st.markdown('<div style="font-size:0.8rem; color:#7f9bb5; margin-top:0.5rem;">Checks for spot colors, page geometry issues, and validates against your black standard.</div>', unsafe_allow_html=True)

    with pf_col2:
        st.markdown('<div style="font-size:0.75rem; color:#7f9bb5; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:0.5rem;">Upload PDF</div>', unsafe_allow_html=True)
        pf_uploaded = st.file_uploader("Drop PDF here for preflight", type=["pdf"], key="pf_upload", label_visibility="collapsed")

        if pf_uploaded:
            st.markdown(f"**File:** `{pf_uploaded.name}`  |  **Size:** {pf_uploaded.size/1024:.1f} KB")
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pf:
                tmp_pf.write(pf_uploaded.read())
                pf_input = tmp_pf.name

            page_info_expander(pf_input)
            st.divider()

            if st.button("▶  Run Preflight", use_container_width=True):
                with st.spinner("Running preflight…"):
                    try:
                        report = ws.preflight_report(pf_input)
                        st.subheader("📋 Preflight Report")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Pages", report["pages"])
                        c2.metric("Spot Colors", len(report["spot_colors"]))
                        c3.metric("Status", "✅ PASS" if report["pass"] else "❌ FAIL")

                        if report["spot_colors"]:
                            st.markdown("**Spot Colors Found:**")
                            for name, label in report["spot_colors"].items():
                                icon = "🔴" if label and "Template" in label else "✂️" if label == "Cut Contour" else "🟡"
                                st.markdown(f"{icon} `{name}` — {label}")

                        for issue in report.get("issues", []):
                            st.markdown(f'<div class="issue-box">❌ {issue}</div>', unsafe_allow_html=True)
                        for warn in report.get("warnings", []):
                            st.markdown(f'<div class="warn-box">⚠️ {warn}</div>', unsafe_allow_html=True)

                        if report["pass"] and not report.get("warnings"):
                            st.markdown('<div class="result-box">✅ File passed all preflight checks.</div>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"❌ {e}")
