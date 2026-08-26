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

BASE_DIR      = Path(__file__).parent
PROFILES_DIR  = BASE_DIR / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)

_QP_EXPORT    = BASE_DIR / "Exported Library from QuickProof Server" / "PDFs"
OVERLAYS_DIR  = _QP_EXPORT / "Overlay"
CUTPATHS_DIR  = _QP_EXPORT / "Cutpath"

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
        border-radius: 50px; padding: 0.5rem 1.5rem;
        font-weight: 600; letter-spacing: 0.02em;
        box-shadow: 0 0 12px rgba(59,130,246,0.35);
        transition: all 0.15s ease;
    }
    .stButton>button:hover { background-color: #60a5fa; box-shadow: 0 0 18px rgba(59,130,246,0.55); }
    /* Download buttons — same pill style */
    .stDownloadButton>button {
        background-color: #1e2a3e; color: #e2e8f0 !important; border: 1px solid rgba(59,130,246,0.4);
        border-radius: 50px; padding: 0.5rem 1.5rem;
        font-weight: 600; letter-spacing: 0.02em;
        transition: all 0.15s ease;
    }
    .stDownloadButton>button:hover {
        background-color: #2d3f5e; color: #fff !important;
        border-color: #3b82f6; box-shadow: 0 0 12px rgba(59,130,246,0.3);
    }
    /* Secondary buttons — keep pill shape but dim them */
    .stButton>button[kind="secondary"] {
        background-color: rgba(59,130,246,0.18) !important; color: #93b4d4 !important;
        border: 1px solid rgba(59,130,246,0.3) !important; box-shadow: none !important;
    }
    .stButton>button[kind="secondary"]:hover {
        background-color: rgba(59,130,246,0.35) !important; color: white !important;
        box-shadow: 0 0 12px rgba(59,130,246,0.3) !important;
    }

    .stSelectbox>div>div, .stNumberInput>div>div>input, .stTextInput>div>div>input,
    .stTextArea textarea {
        background-color: #1e2a3e !important; color: #e2e8f0 !important;
        border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 6px !important;
    }
    /* Selectbox — force white on every possible selector Streamlit generates */
    .stSelectbox *, .stSelectbox *::before, .stSelectbox *::after { color: #e2e8f0 !important; }
    [data-baseweb="select"] { background-color: #1e2a3e !important; }
    [data-baseweb="select"] * { color: #e2e8f0 !important; background-color: #1e2a3e !important; }
    [data-baseweb="select"] input { color: #e2e8f0 !important; }
    [data-baseweb="select"] [data-baseweb="single-value"] { color: #e2e8f0 !important; }
    [data-baseweb="select"] [class*="singleValue"] { color: #e2e8f0 !important; }
    [data-baseweb="select"] [class*="placeholder"] { color: #7f9bb5 !important; }
    [data-baseweb="select"] svg { fill: #e2e8f0 !important; }
    [data-baseweb="popover"] { background-color: #1e2a3e !important; }
    [data-baseweb="menu"] { background-color: #1e2a3e !important; }
    [data-baseweb="menu"] li { background-color: #1e2a3e !important; color: #e2e8f0 !important; }
    [data-baseweb="menu"] li:hover { background-color: #2d3f5e !important; color: #fff !important; }
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

    /* Tab styling — match Upload button exactly */
    .stTabs [data-baseweb="tab-list"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        gap: 8px !important;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.87rem !important;
        padding: 0.48rem 1.4rem !important;
        border: none !important;
        letter-spacing: 0.01em !important;
        opacity: 0.55 !important;
        transition: all 0.15s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        opacity: 0.8 !important;
        box-shadow: 0 0 12px rgba(59,130,246,0.4) !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        opacity: 1 !important;
        box-shadow: 0 0 18px rgba(59,130,246,0.6) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
    .stTabs [data-baseweb="tab-border"]    { display: none !important; }
    .stTabs [data-baseweb="tab-panel"] { padding-top: 1.2rem !important; }
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


def list_pdfs(directory: Path) -> list[str]:
    """Return sorted list of PDF filenames from a directory."""
    if not directory.exists():
        return []
    return sorted(p.name for p in directory.glob("*.pdf"))


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


def recipe_download_buttons(result: dict, stem: str):
    """Render all download buttons for a run_recipe() result dict."""
    outputs = [
        ("preflighted_pdf", f"{stem}_preflighted.pdf",  "application/pdf",  "⬇  Preflighted PDF"),
        ("original_jpeg",   f"{stem}_original.jpg",     "image/jpeg",       "⬇  Original JPEG"),
        ("overlay_pdf",     f"{stem}_overlay.pdf",      "application/pdf",  "⬇  Overlay PDF"),
        ("overlay_jpeg",    f"{stem}_overlay.jpg",      "image/jpeg",       "⬇  Overlay JPEG"),
        ("cutpath_pdf",     f"{stem}_cutpath.pdf",      "application/pdf",  "⬇  Cutpath PDF"),
        ("cutpath_jpeg",    f"{stem}_cutpath.jpg",      "image/jpeg",       "⬇  Cutpath JPEG"),
        ("finished_pdf",    f"{stem}_finished.pdf",     "application/pdf",  "⬇  Finished PDF"),
    ]
    cols = st.columns(2)
    col_idx = 0
    for key, fname, mime, label in outputs:
        val = result.get(key)
        if not val:
            continue
        # val can be a list (jpegs) or a single path string
        paths = val if isinstance(val, list) else [val]
        for path in paths:
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    cols[col_idx % 2].download_button(
                        label, f.read(), file_name=fname, mime=mime,
                        use_container_width=True
                    )
                col_idx += 1


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

    st.divider()
    st.markdown("**Asset Directories**")
    ov_count  = len(list_pdfs(OVERLAYS_DIR))
    cp_count  = len(list_pdfs(CUTPATHS_DIR))
    pf_count  = len(list(PROFILES_DIR.glob("*.json")))
    st.markdown(f"""
    <div style="font-size:0.78rem; color:#7f9bb5; line-height:2;">
        📂 Profiles: <b style="color:#e2e8f0;">{pf_count}</b><br>
        🖼 Overlays: <b style="color:#e2e8f0;">{ov_count}</b><br>
        ✂️ Cutpaths: <b style="color:#e2e8f0;">{cp_count}</b>
    </div>
    """, unsafe_allow_html=True)
    if ov_count == 0:
        st.caption(f"⚠ Overlay folder not found:\n{OVERLAYS_DIR}")
    if cp_count == 0:
        st.caption(f"⚠ Cutpath folder not found:\n{CUTPATHS_DIR}")


# ── Navigation buttons ─────────────────────────────────────────────────────────
if "page" not in st.session_state:
    st.session_state.page = "run"

nav1, nav2, nav3, nav_space = st.columns([1.2, 1.3, 1.5, 5])
_cur = st.session_state.page
with nav1:
    if st.button("▶  Run Profile", use_container_width=True, type="primary" if _cur=="run" else "secondary"):
        st.session_state.page = "run"
        st.rerun()
with nav2:
    if st.button("🔧  Build Profile", use_container_width=True, type="primary" if _cur=="build" else "secondary"):
        st.session_state.page = "build"
        st.rerun()
with nav3:
    if st.button("📋  Preflight Check", use_container_width=True, type="primary" if _cur=="preflight" else "secondary"):
        st.session_state.page = "preflight"
        st.rerun()

st.markdown('<div style="border-bottom:2px solid rgba(59,130,246,0.4); margin:0.6rem 0 1.2rem 0;"></div>', unsafe_allow_html=True)

page = st.session_state.page

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: RUN PROFILE
# ══════════════════════════════════════════════════════════════════════════════
if page == "run":
    all_profiles = load_all_profiles()

    if not all_profiles:
        st.info("No profiles found in the profiles/ folder. Use the **Build Profile** tab to create one.")
    else:
        left, right = st.columns([1, 2])

        with left:
            st.markdown('<div style="font-size:0.72rem; color:#60a5fa; text-transform:uppercase; letter-spacing:0.1em; font-weight:700; margin-bottom:0.4rem;">Select Profile</div>', unsafe_allow_html=True)
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

                is_recipe = profile_data.get("type") == "recipe"
                # Clear stored result if user changed file or profile
                run_key = f"{uploaded.name}|{profile_name}"
                if st.session_state.get("run_key") != run_key:
                    st.session_state.run_key    = run_key
                    st.session_state.run_result = None
                    st.session_state.run_stem   = None

                if st.button(f"▶  Run: {profile_name}", use_container_width=True):
                    with st.spinner(f"Running {profile_name}…"):
                        try:
                            stem = Path(uploaded.name).stem
                            if is_recipe:
                                result = ws.run_recipe(input_path, profile_data,
                                                       profiles_dir=str(PROFILES_DIR),
                                                       overlays_dir=str(OVERLAYS_DIR),
                                                       cutpaths_dir=str(CUTPATHS_DIR))
                                st.session_state.run_result = result
                                st.session_state.run_stem   = stem
                            else:
                                output_path = tempfile.mktemp(suffix=".pdf")
                                ws.run_profile(input_path, output_path, profile_data)
                                st.session_state.run_result = {"finished_pdf": output_path}
                                st.session_state.run_stem   = Path(uploaded.name).stem
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

                # Always render results if they exist for this file+profile combo
                if st.session_state.get("run_result"):
                    success_banner(f"{profile_name} complete")
                    recipe_download_buttons(st.session_state.run_result,
                                            st.session_state.run_stem)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: BUILD PROFILE  (recipe-based)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "build":

    # ── Discover available assets ──────────────────────────────────────────────
    finishing_profiles = {
        data.get("name", p.stem): p.stem
        for p in sorted(PROFILES_DIR.glob("*.json"))
        if (data := json.loads(p.read_text(encoding="utf-8")))
        and data.get("type") != "recipe"   # don't nest recipes
    }
    overlay_files  = ["— none —"] + list_pdfs(OVERLAYS_DIR)
    cutpath_files  = ["— none —"] + list_pdfs(CUTPATHS_DIR)
    finishing_opts = ["— none —"] + list(finishing_profiles.keys())

    # ── Session state ──────────────────────────────────────────────────────────
    for k, v in [("rb_name","New Recipe"), ("rb_desc",""), ("rb_preflight","100k"),
                 ("rb_finishing","— none —"), ("rb_overlay","— none —"),
                 ("rb_cutpath","— none —")]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Load existing recipe ───────────────────────────────────────────────────
    all_recipes = {
        data.get("name", p.stem): (p, data)
        for p in sorted(PROFILES_DIR.glob("*.json"))
        if (data := json.loads(p.read_text(encoding="utf-8")))
        and data.get("type") == "recipe"
    }
    load_opts = ["— start fresh —"] + list(all_recipes.keys())
    lc1, lc2 = st.columns([4, 1])
    with lc1:
        load_choice = st.selectbox("Load existing recipe", load_opts,
                                   label_visibility="collapsed")
    with lc2:
        if st.button("Load →", use_container_width=True) and load_choice != "— start fresh —":
            _, rdata = all_recipes[load_choice]
            st.session_state.rb_name       = rdata.get("name", "")
            st.session_state.rb_desc       = rdata.get("description", "")
            st.session_state.rb_preflight  = rdata.get("preflight", "100k") or "100k"
            # Map stored stems back to display names
            fin_stem = rdata.get("finishing", "")
            fin_name = next((n for n, s in finishing_profiles.items() if s == fin_stem), "— none —")
            st.session_state.rb_finishing  = fin_name
            st.session_state.rb_overlay    = rdata.get("overlay") or "— none —"
            st.session_state.rb_cutpath    = rdata.get("cutpath") or "— none —"
            st.rerun()

    st.divider()

    # ── Recipe fields ──────────────────────────────────────────────────────────
    nm_col, desc_col = st.columns([1, 2])
    with nm_col:
        st.session_state.rb_name = st.text_input("Recipe Name", value=st.session_state.rb_name)
    with desc_col:
        st.session_state.rb_desc = st.text_input("Description", value=st.session_state.rb_desc)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)

    def _stage_header(icon, label, tooltip=""):
        st.markdown(
            f'<div style="font-size:0.68rem; color:#3b82f6; text-transform:uppercase; '
            f'letter-spacing:0.12em; font-weight:700; margin-bottom:0.3rem;">{icon} {label}</div>',
            unsafe_allow_html=True
        )

    c_pf, c_fin, c_ov, c_cp = st.columns(4)

    with c_pf:
        _stage_header("🔍", "Preflight", "Black ink standard")
        pf_opts = ["100k", "75x3"]
        pf_idx  = pf_opts.index(st.session_state.rb_preflight) if st.session_state.rb_preflight in pf_opts else 0
        st.session_state.rb_preflight = st.selectbox(
            "Preflight", pf_opts + ["— skip —"],
            index=pf_idx, label_visibility="collapsed",
            help="100k = (0,0,0,100) · 75x3 = (75,75,75,100)"
        )
        st.markdown(
            '<div style="font-size:0.72rem; color:#7f9bb5; margin-top:0.3rem;">'
            '100k = pure black<br>75x3 = rich black</div>',
            unsafe_allow_html=True
        )

    with c_fin:
        _stage_header("⚙️", "Finishing", "Python finishing profile")
        fin_idx = finishing_opts.index(st.session_state.rb_finishing) \
                  if st.session_state.rb_finishing in finishing_opts else 0
        st.session_state.rb_finishing = st.selectbox(
            "Finishing", finishing_opts,
            index=fin_idx, label_visibility="collapsed"
        )
        if st.session_state.rb_finishing != "— none —":
            st.markdown(
                f'<div style="font-size:0.72rem; color:#7f9bb5; margin-top:0.3rem;">'
                f'{finishing_profiles.get(st.session_state.rb_finishing,"")}.json</div>',
                unsafe_allow_html=True
            )

    with c_ov:
        _stage_header("🖼", "Overlay", "Template overlay PDF")
        ov_idx = overlay_files.index(st.session_state.rb_overlay) \
                 if st.session_state.rb_overlay in overlay_files else 0
        st.session_state.rb_overlay = st.selectbox(
            "Overlay", overlay_files,
            index=ov_idx, label_visibility="collapsed"
        )
        if not OVERLAYS_DIR.exists():
            st.caption("⚠ Overlay folder missing")

    with c_cp:
        _stage_header("✂️", "Cutpath", "Die cut path PDF")
        cp_idx = cutpath_files.index(st.session_state.rb_cutpath) \
                 if st.session_state.rb_cutpath in cutpath_files else 0
        st.session_state.rb_cutpath = st.selectbox(
            "Cutpath", cutpath_files,
            index=cp_idx, label_visibility="collapsed"
        )
        if not CUTPATHS_DIR.exists():
            st.caption("⚠ Cutpath folder missing")

    # ── Recipe preview ─────────────────────────────────────────────────────────
    st.divider()
    stages_defined = [
        s for s in [
            st.session_state.rb_preflight  if st.session_state.rb_preflight  != "— skip —" else None,
            st.session_state.rb_finishing  if st.session_state.rb_finishing  != "— none —" else None,
            st.session_state.rb_overlay    if st.session_state.rb_overlay    != "— none —" else None,
            st.session_state.rb_cutpath    if st.session_state.rb_cutpath    != "— none —" else None,
        ] if s
    ]
    st.markdown(
        f'<div style="font-size:0.75rem; color:#7f9bb5; margin-bottom:0.5rem;">'
        f'Pipeline: <b style="color:#e2e8f0;">'
        + " → ".join(stages_defined or ["(nothing selected)"])
        + "</b></div>",
        unsafe_allow_html=True
    )

    # ── Save + Test ────────────────────────────────────────────────────────────
    sv_col, cl_col = st.columns([3, 1])
    with sv_col:
        if st.button("💾  Save Recipe", use_container_width=True, disabled=not stages_defined):
            if not st.session_state.rb_name.strip():
                st.error("Give the recipe a name first.")
            else:
                recipe_to_save = {
                    "type":        "recipe",
                    "name":        st.session_state.rb_name.strip(),
                    "description": st.session_state.rb_desc.strip(),
                    "preflight":   st.session_state.rb_preflight if st.session_state.rb_preflight != "— skip —" else None,
                    "finishing":   finishing_profiles.get(st.session_state.rb_finishing) if st.session_state.rb_finishing != "— none —" else None,
                    "overlay":     st.session_state.rb_overlay   if st.session_state.rb_overlay   != "— none —" else None,
                    "cutpath":     st.session_state.rb_cutpath   if st.session_state.rb_cutpath   != "— none —" else None,
                }
                saved = save_profile_to_disk(recipe_to_save)
                st.success(f"Saved → {saved.name}")
    with cl_col:
        if st.button("🗑  Clear", use_container_width=True):
            for k, v in [("rb_name","New Recipe"), ("rb_desc",""), ("rb_preflight","100k"),
                         ("rb_finishing","— none —"), ("rb_overlay","— none —"), ("rb_cutpath","— none —")]:
                st.session_state[k] = v
            st.rerun()

    # ── Test run ───────────────────────────────────────────────────────────────
    if stages_defined:
        st.divider()
        st.markdown("#### Test Run")
        test_up = st.file_uploader("Upload a PDF to test this recipe",
                                   type=["pdf"], key="recipe_test_upload")
        if test_up:
            # Clear stored result if file changes
            btest_key = f"btest|{test_up.name}|{st.session_state.rb_name}"
            if st.session_state.get("btest_key") != btest_key:
                st.session_state.btest_key    = btest_key
                st.session_state.btest_result = None
                st.session_state.btest_stem   = None

            if st.button("▶  Test Recipe", use_container_width=True):
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
                    tmp_in.write(test_up.read())
                    t_in = tmp_in.name
                test_recipe = {
                    "type":      "recipe",
                    "name":      st.session_state.rb_name,
                    "preflight": st.session_state.rb_preflight if st.session_state.rb_preflight != "— skip —" else None,
                    "finishing": finishing_profiles.get(st.session_state.rb_finishing) if st.session_state.rb_finishing != "— none —" else None,
                    "overlay":   st.session_state.rb_overlay  if st.session_state.rb_overlay  != "— none —" else None,
                    "cutpath":   st.session_state.rb_cutpath  if st.session_state.rb_cutpath  != "— none —" else None,
                }
                with st.spinner("Running recipe…"):
                    try:
                        result = ws.run_recipe(t_in, test_recipe,
                                               profiles_dir=str(PROFILES_DIR),
                                               overlays_dir=str(OVERLAYS_DIR),
                                               cutpaths_dir=str(CUTPATHS_DIR))
                        st.session_state.btest_result = result
                        st.session_state.btest_stem   = Path(test_up.name).stem
                    except Exception as e:
                        st.error(f"❌ {e}")

            if st.session_state.get("btest_result"):
                success_banner("Recipe test complete")
                recipe_download_buttons(st.session_state.btest_result,
                                        st.session_state.btest_stem)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: PREFLIGHT CHECK
# ══════════════════════════════════════════════════════════════════════════════
elif page == "preflight":
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
