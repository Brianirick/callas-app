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

GITHUB_REPO   = "Brianirick/callas-app"

def _github_upload(repo_path: str, file_bytes: bytes, commit_msg: str):
    """Commit a file to GitHub so it persists after Streamlit Cloud reboots.
    Requires GITHUB_TOKEN in st.secrets. Silently skips if token not configured."""
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        if not token:
            return
        from github import Github
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO)
        try:
            existing = repo.get_contents(repo_path)
            repo.update_file(repo_path, commit_msg, file_bytes, existing.sha)
        except Exception:
            repo.create_file(repo_path, commit_msg, file_bytes)
    except Exception as e:
        st.warning(f"GitHub sync skipped: {e}")

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
    /* Disabled buttons — dark background so arrows/text stay visible */
    .stButton>button:disabled, .stButton>button[disabled] {
        background-color: #1a2535 !important; color: #3d5068 !important;
        border: 1px solid rgba(59,130,246,0.1) !important;
        box-shadow: none !important; opacity: 1 !important;
    }

    .stSelectbox>div>div, .stNumberInput>div>div>input, .stTextInput>div>div>input,
    .stTextArea textarea {
        background-color: #1e2a3e !important; color: #e2e8f0 !important;
        border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 6px !important;
    }
    /* Text area — all possible selectors */
    .stTextArea, .stTextArea > div, .stTextArea > div > div,
    .stTextArea > label + div, .stTextArea > label + div > div { background-color: #1e2a3e !important; }
    [data-baseweb="textarea"], [data-baseweb="base-input"],
    [data-baseweb="textarea"] textarea, [data-baseweb="base-input"] textarea,
    textarea { background-color: #1e2a3e !important; color: #e2e8f0 !important; }
    textarea::placeholder { color: #4a6080 !important; }
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
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzoneInstructions"] small,
    [data-testid="stFileUploaderDropzoneInstructions"] span { color: #4a6080 !important; }

    .streamlit-expanderHeader { background-color: #1a2540 !important; color: #e2e8f0 !important; border-radius: 6px; }
    .streamlit-expanderContent { background-color: #161f31 !important; border: 1px solid rgba(255,255,255,0.06); border-radius: 0 0 6px 6px; }
    /* Newer Streamlit expander selectors */
    [data-testid="stExpander"] { background-color: #1a2540 !important; border: 1px solid rgba(255,255,255,0.08) !important; border-radius: 6px !important; }
    [data-testid="stExpander"] details { background-color: #1a2540 !important; }
    [data-testid="stExpander"] summary { background-color: #1a2540 !important; color: #e2e8f0 !important; }
    [data-testid="stExpander"] summary:hover { background-color: #1e2f4a !important; }
    [data-testid="stExpander"] summary * { color: #e2e8f0 !important; }
    [data-testid="stExpander"] summary svg { fill: #e2e8f0 !important; }
    [data-testid="stExpanderDetails"] { background-color: #161f31 !important; color: #e2e8f0 !important; }
    [data-testid="stExpanderDetails"] * { color: #e2e8f0 !important; }

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
                        use_container_width=True,
                        key=f"dl_{key}_{col_idx}_{stem}"
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
                st.markdown(f'<div class="info-box">{desc}</div>', unsafe_allow_html=True)

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
                # Auto-run whenever file or profile changes
                run_key = f"{uploaded.name}|{profile_name}"
                if st.session_state.get("run_key") != run_key:
                    st.session_state.run_key    = run_key
                    st.session_state.run_result = None
                    st.session_state.run_stem   = None
                    with st.status(f"Processing {profile_name}…", expanded=True) as _status:
                        try:
                            stem = Path(uploaded.name).stem
                            if is_recipe:
                                result = ws.run_recipe(input_path, profile_data,
                                                       profiles_dir=str(PROFILES_DIR),
                                                       overlays_dir=str(OVERLAYS_DIR),
                                                       cutpaths_dir=str(CUTPATHS_DIR),
                                                       status_cb=lambda msg: st.write(msg))
                                st.session_state.run_result = result
                                st.session_state.run_stem   = stem
                            else:
                                st.write("⚙️ Running finishing profile…")
                                output_path = tempfile.mktemp(suffix=".pdf")
                                ws.run_profile(input_path, output_path, profile_data)
                                st.write("✅ Done!")
                                st.session_state.run_result = {"finished_pdf": output_path}
                                st.session_state.run_stem   = Path(uploaded.name).stem
                            _status.update(label=f"✅ {profile_name} complete!", state="complete", expanded=False)
                        except Exception as e:
                            _status.update(label="❌ Error", state="error")
                            st.error(f"Error: {e}")

                # Always render results if they exist for this file+profile combo
                if st.session_state.get("run_result"):
                    result = st.session_state.run_result
                    # Page size check results
                    sz_results = result.get("check_size_results", [])
                    if sz_results:
                        all_pass = all(r.get("passed", True) for r in sz_results)
                        label = "✅ Page Size Check" if all_pass else "❌ Page Size Check"
                        with st.expander(label, expanded=not all_pass):
                            for r in sz_results:
                                icon = "✅" if r.get("passed", True) else "❌"
                                st.markdown(f"{icon}  {r['message']}")
                    success_banner(f"{profile_name} complete")
                    recipe_download_buttons(result, st.session_state.run_stem)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: BUILD PROFILE  (recipe-based)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "build":

    # ── Sub-mode toggle ────────────────────────────────────────────────────────
    if "bp_mode" not in st.session_state:
        st.session_state.bp_mode = "recipe"
    _bmode = st.session_state.bp_mode
    _bm1, _bm2, _bm_sp = st.columns([1.1, 1.8, 5])
    with _bm1:
        if st.button("📋  Recipe", use_container_width=True,
                     type="primary" if _bmode == "recipe" else "secondary",
                     key="bm_recipe"):
            st.session_state.bp_mode = "recipe"
            st.rerun()
    with _bm2:
        if st.button("🔩  Finishing Profile", use_container_width=True,
                     type="primary" if _bmode == "finishing" else "secondary",
                     key="bm_finishing"):
            st.session_state.bp_mode = "finishing"
            st.rerun()
    st.markdown('<div style="margin-bottom:0.25rem;"></div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # FINISHING PROFILE BUILDER
    # ══════════════════════════════════════════════════════════════════════════
    if _bmode == "finishing":

        # Init session state
        for _k, _v in [("fp_steps", []), ("fp_name", "New Finishing Profile"),
                       ("fp_desc", ""), ("fp_op_type", "fixup")]:
            if _k not in st.session_state:
                st.session_state[_k] = _v

        # Load existing finishing profile
        _all_fps = {
            data.get("name", p.stem): (p, data)
            for p in sorted(PROFILES_DIR.glob("*.json"))
            if (data := json.loads(p.read_text(encoding="utf-8")))
            and data.get("type") != "recipe"
        }
        _fl1, _fl2 = st.columns([4, 1])
        with _fl1:
            _fp_load_choice = st.selectbox("Load existing finishing profile",
                                           ["— start fresh —"] + list(_all_fps.keys()),
                                           label_visibility="collapsed", key="fp_load_sel")
        with _fl2:
            if st.button("Load →", use_container_width=True, key="fp_load_btn") \
               and _fp_load_choice != "— start fresh —":
                _, _fpdata = _all_fps[_fp_load_choice]
                st.session_state.fp_name  = _fpdata.get("name", "")
                st.session_state.fp_desc  = _fpdata.get("description", "")
                st.session_state.fp_steps = _fpdata.get("steps", [])
                st.rerun()

        st.divider()

        # Name / Description
        _fn1, _fn2 = st.columns([1, 2])
        with _fn1:
            st.session_state.fp_name = st.text_input(
                "Profile Name", value=st.session_state.fp_name, key="fp_name_inp")
        with _fn2:
            st.session_state.fp_desc = st.text_input(
                "Description",  value=st.session_state.fp_desc, key="fp_desc_inp")

        st.markdown('<div style="margin-top:0.4rem;"></div>', unsafe_allow_html=True)

        # ── Two-column builder ─────────────────────────────────────────────────
        _add_col, _steps_col = st.columns([1, 1.2])

        with _add_col:
            st.markdown(
                '<div style="font-size:0.68rem; color:#3b82f6; text-transform:uppercase;'
                'letter-spacing:0.12em; font-weight:700; margin-bottom:0.6rem;">➕ Add Step</div>',
                unsafe_allow_html=True
            )
            _ta, _tb = st.columns(2)
            with _ta:
                if st.button("🔧 Fixup", use_container_width=True, key="fp_t_fixup",
                             type="primary" if st.session_state.fp_op_type == "fixup" else "secondary"):
                    st.session_state.fp_op_type = "fixup"
                    st.rerun()
            with _tb:
                if st.button("🔍 Check", use_container_width=True, key="fp_t_check",
                             type="primary" if st.session_state.fp_op_type == "check" else "secondary"):
                    st.session_state.fp_op_type = "check"
                    st.rerun()

            _catalog = ws.AVAILABLE_OPS if st.session_state.fp_op_type == "fixup" else ws.AVAILABLE_CHECKS
            _cats    = sorted({v["category"] for v in _catalog.values()})
            _sel_cat = st.selectbox("Category", ["All"] + _cats, key="fp_cat_sel")

            _ops_filtered = {k: v for k, v in _catalog.items()
                             if _sel_cat == "All" or v["category"] == _sel_cat}
            _op_ids    = list(_ops_filtered.keys())
            _op_labels = [_ops_filtered[k]["label"] for k in _op_ids]

            if not _op_ids:
                st.caption("No operations in this category.")
            else:
                _sel_op_idx = st.selectbox("Operation", range(len(_op_ids)),
                                           format_func=lambda i: _op_labels[i],
                                           key="fp_op_sel")
                _sel_op_id   = _op_ids[_sel_op_idx]
                _sel_op_meta = _ops_filtered[_sel_op_id]
                st.markdown(
                    f'<div style="font-size:0.71rem; color:#7f9bb5; margin-bottom:0.35rem;">'
                    f'{_sel_op_meta.get("description","")}</div>',
                    unsafe_allow_html=True
                )

                # Dynamic param inputs
                _pvals = {}
                for _pm in _sel_op_meta.get("params", []):
                    _pk = f"fp_p_{_sel_op_id}_{_pm['name']}"
                    if _pm["type"] == "float":
                        _pvals[_pm["name"]] = st.number_input(
                            _pm["label"], value=float(_pm.get("default", 0.0)),
                            step=float(_pm.get("step", 0.01)), format="%.4f", key=_pk)
                    elif _pm["type"] == "int":
                        _pvals[_pm["name"]] = int(st.number_input(
                            _pm["label"], value=int(_pm.get("default", 0)), step=1, key=_pk))
                    elif _pm["type"] == "select":
                        _opts = _pm["options"]
                        _def_idx = _opts.index(_pm["default"]) if _pm.get("default") in _opts else 0
                        _pvals[_pm["name"]] = st.selectbox(_pm["label"], _opts, index=_def_idx, key=_pk)
                    elif _pm["type"] == "bool":
                        _pvals[_pm["name"]] = st.checkbox(
                            _pm["label"], value=bool(_pm.get("default", False)), key=_pk)
                    else:
                        _pvals[_pm["name"]] = st.text_input(
                            _pm["label"], value=str(_pm.get("default", "")), key=_pk)

                _btn_lbl = ("🔧 Add Fixup Step" if st.session_state.fp_op_type == "fixup"
                            else "🔍 Add Check Step")
                if st.button(_btn_lbl, use_container_width=True, type="primary", key="fp_add_btn"):
                    _new_step = {"op": _sel_op_id}
                    if st.session_state.fp_op_type == "check":
                        _new_step["type"] = "check"
                    if _pvals:
                        _new_step["params"] = _pvals
                    st.session_state.fp_steps.append(_new_step)
                    st.rerun()

        with _steps_col:
            st.markdown(
                '<div style="font-size:0.68rem; color:#3b82f6; text-transform:uppercase;'
                'letter-spacing:0.12em; font-weight:700; margin-bottom:0.6rem;">📋 Profile Steps</div>',
                unsafe_allow_html=True
            )
            if not st.session_state.fp_steps:
                st.caption("No steps yet — add one from the left.")
            else:
                for _si, _step in enumerate(st.session_state.fp_steps):
                    _is_chk   = _step.get("type") == "check"
                    _cat_ref  = ws.AVAILABLE_CHECKS if _is_chk else ws.AVAILABLE_OPS
                    _sm       = _cat_ref.get(_step["op"], {})
                    _slabel   = _sm.get("label", _step["op"])
                    _badge_c  = "#3b82f6" if _is_chk else "#f97316"
                    _badge_t  = "CHECK"   if _is_chk else "FIXUP"
                    _pstr     = (", ".join(f"{k}={v}" for k, v in _step["params"].items())
                                 if _step.get("params") else "")
                    _rc1, _rup, _rdn, _rc2 = st.columns([6, 0.6, 0.6, 0.7])
                    with _rc1:
                        st.markdown(
                            f'<div style="background:#1e2a3a;border-radius:6px;padding:7px 11px;'
                            f'margin-bottom:5px;border-left:3px solid {_badge_c};">'
                            f'<span style="font-size:0.60rem;color:{_badge_c};text-transform:uppercase;'
                            f'font-weight:700;letter-spacing:0.1em;">{_badge_t}</span>'
                            f'<span style="font-size:0.72rem;color:#e2e8f0;margin-left:8px;font-weight:600;">'
                            f'{_si+1}. {_slabel}</span>'
                            + (f'<div style="font-size:0.64rem;color:#7f9bb5;margin-top:2px;">{_pstr}</div>'
                               if _pstr else "")
                            + "</div>",
                            unsafe_allow_html=True
                        )
                    with _rup:
                        if st.button("↑", key=f"fp_up_{_si}", help="Move up",
                                     type="primary", disabled=_si == 0):
                            _s = st.session_state.fp_steps
                            _s[_si - 1], _s[_si] = _s[_si], _s[_si - 1]
                            st.rerun()
                    with _rdn:
                        if st.button("↓", key=f"fp_dn_{_si}", help="Move down",
                                     type="primary",
                                     disabled=_si == len(st.session_state.fp_steps) - 1):
                            _s = st.session_state.fp_steps
                            _s[_si + 1], _s[_si] = _s[_si], _s[_si + 1]
                            st.rerun()
                    with _rc2:
                        if st.button("✕", key=f"fp_rm_{_si}", help="Remove",
                                     type="primary"):
                            st.session_state.fp_steps.pop(_si)
                            st.rerun()

            st.markdown('<div style="margin-top:0.7rem;"></div>', unsafe_allow_html=True)
            _fsv, _fcl = st.columns([3, 1])
            with _fsv:
                if st.button("💾  Save Profile", use_container_width=True, key="fp_save_btn",
                             disabled=not st.session_state.fp_steps):
                    if not st.session_state.fp_name.strip():
                        st.error("Give the profile a name first.")
                    else:
                        _saved = save_profile_to_disk({
                            "name":        st.session_state.fp_name.strip(),
                            "description": st.session_state.fp_desc.strip(),
                            "steps":       st.session_state.fp_steps,
                        })
                        st.success(f"Saved → {_saved.name}")
            with _fcl:
                if st.button("🗑  Clear", use_container_width=True, key="fp_clear_btn"):
                    st.session_state.fp_steps = []
                    st.session_state.fp_name  = "New Finishing Profile"
                    st.session_state.fp_desc  = ""
                    st.rerun()

        # ── Test run ─────────────────────────────────────────────────────────
        if st.session_state.fp_steps:
            st.divider()
            st.markdown("#### Test Run")
            _fp_up = st.file_uploader("Upload a PDF to test this profile",
                                      type=["pdf"], key="fp_test_up")
            if _fp_up:
                _fptest_key = f"fptest|{_fp_up.name}|{st.session_state.fp_name}"
                if st.session_state.get("fptest_key") != _fptest_key:
                    st.session_state.fptest_key    = _fptest_key
                    st.session_state.fptest_result = None

                if st.button("▶  Test Profile", use_container_width=True, key="fp_run_btn"):
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as _ti:
                        _ti.write(_fp_up.read())
                        _t_in = _ti.name
                    _t_out = tempfile.mktemp(suffix=".pdf")
                    with st.spinner("Running profile…"):
                        try:
                            _fpr = ws.run_profile(_t_in, _t_out, {
                                "name":  st.session_state.fp_name,
                                "steps": st.session_state.fp_steps,
                            })
                            st.session_state.fptest_result = _fpr
                        except Exception as _fpe:
                            st.error(f"❌ {_fpe}")

                if st.session_state.get("fptest_result"):
                    _fpr = st.session_state.fptest_result
                    success_banner("Profile test complete")
                    _fp_out = _fpr.get("output_path")
                    if _fp_out and Path(_fp_out).exists():
                        _stem = Path(_fp_up.name).stem
                        st.download_button(
                            "⬇  Download Finished PDF",
                            data=open(_fp_out, "rb").read(),
                            file_name=f"{_stem}_finished.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="fp_dl_btn",
                        )
                    _chk_res = _fpr.get("check_results", [])
                    if _chk_res:
                        st.markdown("**Check Results:**")
                        for _chk in _chk_res:
                            _all_pass = all(r.get("passed", True) for r in _chk["results"])
                            with st.expander(f"{'✅' if _all_pass else '❌'}  {_chk['label']}"):
                                for _cr in _chk["results"]:
                                    st.markdown(
                                        f"{'✅' if _cr.get('passed', True) else '❌'}  {_cr['message']}")

        st.stop()   # don't render recipe builder below

    # ═══════════════════════════════════════════════════════════════════════════
    # RECIPE BUILDER (existing)
    # ═══════════════════════════════════════════════════════════════════════════

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
    for k, v in [("rb_name","New Recipe"), ("rb_desc",""), ("rb_preflight","60-50-50-100"),
                 ("rb_finishing","— none —"), ("rb_overlay","— none —"),
                 ("rb_cutpath","— none —"), ("rb_check_size", True),
                 ("rb_width", 0.0), ("rb_height", 0.0), ("rb_tol", 0.1)]:
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
            # normalise legacy keys
            _pf_raw = rdata.get("preflight") or "60-50-50-100"
            _pf_map = {"100k": "60-50-50-100", "75x3": "75-75-75-100"}
            st.session_state.rb_preflight  = _pf_map.get(_pf_raw, _pf_raw)
            # Map stored stems back to display names
            fin_stem = rdata.get("finishing", "")
            fin_name = next((n for n, s in finishing_profiles.items() if s == fin_stem), "— none —")
            st.session_state.rb_finishing  = fin_name
            st.session_state.rb_overlay    = rdata.get("overlay") or "— none —"
            st.session_state.rb_cutpath    = rdata.get("cutpath") or "— none —"
            _sz = rdata.get("check_size") or {}
            st.session_state.rb_check_size = bool(_sz)
            st.session_state.rb_width      = float(_sz.get("width_inch", 0.0))
            st.session_state.rb_height     = float(_sz.get("height_inch", 0.0))
            st.session_state.rb_tol        = float(_sz.get("tolerance_inch", 0.1))
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
        pf_opts = ["60-50-50-100", "75-75-75-100"]
        pf_idx  = pf_opts.index(st.session_state.rb_preflight) if st.session_state.rb_preflight in pf_opts else 0
        st.session_state.rb_preflight = st.selectbox(
            "Preflight", pf_opts + ["— skip —"],
            index=pf_idx, label_visibility="collapsed",
            help="60-50-50-100 = WS Display standard · 75-75-75-100 = rich black"
        )
        st.markdown(
            '<div style="font-size:0.72rem; color:#7f9bb5; margin-top:0.3rem;">'
            '60-50-50-100 = WS standard<br>75-75-75-100 = rich black</div>',
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

    # ── Page size check ────────────────────────────────────────────────────────
    st.markdown('<div style="margin-top:0.75rem;"></div>', unsafe_allow_html=True)
    _chk_header, _chk_rest = st.columns([1, 3])
    with _chk_header:
        st.session_state.rb_check_size = st.checkbox(
            "📐  Check page size",
            value=st.session_state.rb_check_size
        )
    if st.session_state.rb_check_size:
        with _chk_rest:
            _sz1, _sz2, _sz3 = st.columns(3)
            with _sz1:
                st.session_state.rb_width = st.number_input(
                    "Width (in)", value=st.session_state.rb_width,
                    min_value=0.0, step=0.25, format="%.2f")
            with _sz2:
                st.session_state.rb_height = st.number_input(
                    "Height (in)", value=st.session_state.rb_height,
                    min_value=0.0, step=0.25, format="%.2f")
            with _sz3:
                st.session_state.rb_tol = st.number_input(
                    "Tolerance (in)", value=st.session_state.rb_tol,
                    min_value=0.0, step=0.05, format="%.2f")

    # ── Upload new overlay / cutpath ───────────────────────────────────────────
    with st.expander("📤  Upload New Overlay / Cutpath"):
        up_col1, up_col2 = st.columns(2)
        with up_col1:
            st.caption("Overlay PDF")
            ov_upload = st.file_uploader("Upload overlay", type=["pdf"],
                                         key="ov_uploader", label_visibility="collapsed")
            if ov_upload and st.button("Save Overlay", key="save_ov"):
                OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
                dest = OVERLAYS_DIR / ov_upload.name
                dest.write_bytes(ov_upload.read())
                _github_upload(f"Exported Library from QuickProof Server/PDFs/Overlay/{ov_upload.name}",
                               dest.read_bytes(), f"Upload overlay: {ov_upload.name}")
                st.success(f"Saved {ov_upload.name}")
                st.rerun()
        with up_col2:
            st.caption("Cutpath PDF")
            cp_upload = st.file_uploader("Upload cutpath", type=["pdf"],
                                         key="cp_uploader", label_visibility="collapsed")
            if cp_upload and st.button("Save Cutpath", key="save_cp"):
                CUTPATHS_DIR.mkdir(parents=True, exist_ok=True)
                dest = CUTPATHS_DIR / cp_upload.name
                dest.write_bytes(cp_upload.read())
                _github_upload(f"Exported Library from QuickProof Server/PDFs/Cutpath/{cp_upload.name}",
                               dest.read_bytes(), f"Upload cutpath: {cp_upload.name}")
                st.success(f"Saved {cp_upload.name}")
                st.rerun()

    # ── Recipe preview ─────────────────────────────────────────────────────────
    st.divider()
    stages_defined = [
        s for s in [
            st.session_state.rb_preflight  if st.session_state.rb_preflight  != "— skip —" else None,
            (f"check {st.session_state.rb_width}×{st.session_state.rb_height}in"
             if st.session_state.rb_check_size and st.session_state.rb_width and st.session_state.rb_height
             else None),
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
                    "check_size":  {
                        "width_inch":     st.session_state.rb_width,
                        "height_inch":    st.session_state.rb_height,
                        "tolerance_inch": st.session_state.rb_tol,
                    } if st.session_state.rb_check_size and st.session_state.rb_width and st.session_state.rb_height else None,
                    "finishing":   finishing_profiles.get(st.session_state.rb_finishing) if st.session_state.rb_finishing != "— none —" else None,
                    "overlay":     st.session_state.rb_overlay   if st.session_state.rb_overlay   != "— none —" else None,
                    "cutpath":     st.session_state.rb_cutpath   if st.session_state.rb_cutpath   != "— none —" else None,
                }
                saved = save_profile_to_disk(recipe_to_save)
                st.success(f"Saved → {saved.name}")
    with cl_col:
        if st.button("🗑  Clear", use_container_width=True):
            for k, v in [("rb_name","New Recipe"), ("rb_desc",""), ("rb_preflight","60-50-50-100"),
                         ("rb_finishing","— none —"), ("rb_overlay","— none —"), ("rb_cutpath","— none —"),
                         ("rb_check_size", True), ("rb_width", 0.0), ("rb_height", 0.0), ("rb_tol", 0.1)]:
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
        black_target = st.selectbox("Black ink target", ["60-50-50-100", "75-75-75-100"],
                                    help="60-50-50-100 = WS Display standard. 75-75-75-100 = rich black.")
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
