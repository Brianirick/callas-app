"""
ws_app.py
WS Display PDF Tools — Streamlit App

Run with:
    streamlit run ws_app.py
"""

import streamlit as st
import tempfile
import os
import sys
from pathlib import Path

# Make sure ws_pdf_tools is importable from same folder
sys.path.insert(0, str(Path(__file__).parent))
import importlib
import ws_pdf_tools as ws
importlib.reload(ws)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CallasFlow",
    page_icon="📄",
    layout="wide",
)

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Base dark navy theme (PSUFlow-style) ── */
    .stApp { background-color: #0f1623; }
    .main .block-container { background-color: #0f1623; padding-top: 1.5rem; }
    section[data-testid="stSidebar"] { background-color: #131d2e; border-right: 1px solid rgba(255,255,255,0.08); }
    section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

    /* ── Text ── */
    h1, h2, h3, h4, p, label, div { color: #e2e8f0; }
    .stMarkdown p { color: #b0bec5; }

    /* ── Buttons ── */
    .stButton>button {
        background-color: #3b82f6;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        box-shadow: 0 0 12px rgba(59,130,246,0.35);
        transition: all 0.15s ease;
    }
    .stButton>button:hover {
        background-color: #60a5fa;
        box-shadow: 0 0 18px rgba(59,130,246,0.55);
    }

    /* ── Selectbox / inputs ── */
    .stSelectbox>div>div, .stNumberInput>div>div>input, .stTextInput>div>div>input {
        background-color: #1e2a3e !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 6px !important;
    }
    /* Dropdown popup menu — broad override for Streamlit cloud */
    [data-baseweb="popover"] { background-color: #1e2a3e !important; }
    [data-baseweb="menu"] { background-color: #1e2a3e !important; }
    [data-baseweb="menu"] ul { background-color: #1e2a3e !important; }
    [data-baseweb="menu"] li { background-color: #1e2a3e !important; color: #e2e8f0 !important; }
    [data-baseweb="menu"] li:hover { background-color: #2d3f5e !important; color: #ffffff !important; }
    [data-baseweb="select"] div { color: #e2e8f0 !important; }
    [data-baseweb="select"] span { color: #e2e8f0 !important; }
    /* Catch-all for any popup/dropdown text */
    [role="listbox"] { background-color: #1e2a3e !important; }
    [role="option"] { background-color: #1e2a3e !important; color: #e2e8f0 !important; }
    [role="option"]:hover { background-color: #2d3f5e !important; color: #ffffff !important; }
    ul[role="listbox"] li { color: #e2e8f0 !important; background-color: #1e2a3e !important; }

    /* ── Top accent bar ── */
    .stApp::before {
        content: '';
        display: block;
        height: 3px;
        background: linear-gradient(90deg, #3b82f6, #60a5fa, #2563eb);
        position: fixed;
        top: 0; left: 0; right: 0;
        z-index: 9999;
    }

    /* ── File uploader ── */
    .stFileUploader {
        background-color: #1a2540;
        border: 1px dashed rgba(59,130,246,0.4);
        border-radius: 8px;
        padding: 0.5rem;
    }
    .stFileUploader label { color: #7f9bb5 !important; }
    [data-testid="stFileUploaderDropzone"] {
        background-color: #1a2540 !important;
        border: none !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        background-color: #3b82f6 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
    }
    [data-testid="stFileUploaderDropzone"] button:hover {
        background-color: #60a5fa !important;
    }

    /* ── Expander ── */
    .streamlit-expanderHeader { background-color: #1a2540 !important; color: #e2e8f0 !important; border-radius: 6px; }
    .streamlit-expanderContent { background-color: #161f31 !important; border: 1px solid rgba(255,255,255,0.06); border-radius: 0 0 6px 6px; }

    /* ── Divider ── */
    hr { border-color: rgba(255,255,255,0.08) !important; }

    /* ── Caption/footer ── */
    .stCaption, footer { color: #4a6080 !important; }

    /* ── Spinner ── */
    .stSpinner > div { border-top-color: #3b82f6 !important; }

    /* ── Metric cards ── */
    [data-testid="metric-container"] {
        background-color: #1a2540;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 0.75rem 1rem;
    }
    [data-testid="metric-container"] label { color: #7f9bb5 !important; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.6rem !important; font-weight: 700; }

    /* ── Status boxes ── */
    .result-box {
        background: rgba(34, 197, 94, 0.1);
        border-left: 4px solid #22c55e;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        color: #e2e8f0;
    }
    .issue-box {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        color: #e2e8f0;
    }
    .warn-box {
        background: rgba(234, 179, 8, 0.1);
        border-left: 4px solid #eab308;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        color: #e2e8f0;
    }
    .info-box {
        background: rgba(37, 99, 235, 0.1);
        border-left: 4px solid #2563eb;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        color: #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex; align-items:center; gap:1.2rem; padding:0.5rem 0 1.2rem 0;
            border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:1.8rem;">
    <div style="background:linear-gradient(135deg,#1d4ed8,#3b82f6); width:72px; height:72px; border-radius:14px;
                display:flex; align-items:center; justify-content:center; font-size:1.6rem; font-weight:900;
                color:white; letter-spacing:-0.03em; flex-shrink:0;
                box-shadow:0 0 28px rgba(59,130,246,0.5), 0 4px 12px rgba(0,0,0,0.4);">CF</div>
    <div>
        <div style="font-size:1.7rem; font-weight:800; color:#ffffff; letter-spacing:-0.02em; line-height:1.1;">CallasFlow</div>
        <div style="font-size:0.72rem; color:#3b82f6; letter-spacing:0.12em; text-transform:uppercase; font-weight:600; margin-top:2px;">
            WS Display &nbsp;·&nbsp; PDF Finishing &nbsp;·&nbsp; Preflight &nbsp;·&nbsp; Preparation
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

OP_DESCRIPTIONS = {
    "Preflight Check":                "Scans for template spot colors, font issues, and page geometry problems before going to press.",
    "Outline Fonts + Clean Metadata": "Converts all fonts to curves (no font dependencies) and strips private application data.",
    "Set TrimBox":                    "Applies the correct trim dimensions using built-in presets for your product line.",
    "Set MediaBox to Origin":         "Normalizes the page so its lower-left corner sits at 0,0 — required before most finishing steps.",
    "Create Identical Pages":         "Duplicates a single-page file to N identical pages for gang printing.",
    "Remove Bleed":                   "Sets the CropBox equal to the TrimBox, hiding bleed area from output.",
    "Full Finishing — 10ft Tent":          "Full pipeline: origin → artwork layer → cutpath layer → 118\"×86.25\" crop.",
    "Full Finishing — 6ft Multi-Page":     "Full pipeline: duplicate to 5 pages → correct page geometry.",
    "Full Finishing — SLD 4.2 Top/Bottom": "Full SLD pipeline: origin → TrimBox stroke → enlarge +4.5\" top/bottom → BleedBox from CropBox → thru-cut spot at BleedBox.",
}

# ── Sidebar — Operation Selector ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:0.6rem 0 1rem 0; border-bottom:1px solid rgba(255,255,255,0.08); margin-bottom:1rem;">
        <div style="font-size:0.65rem; color:#3b82f6; letter-spacing:0.14em; text-transform:uppercase; font-weight:700;">PDF AUTOMATION SUITE</div>
        <div style="font-size:0.62rem; color:#4a6080; margin-top:2px;">v1.0 &nbsp;·&nbsp; WS Display</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.75rem; color:#7f9bb5; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:0.4rem;">Select Profile</div>', unsafe_allow_html=True)
    operation = st.selectbox(
        "Select profile",
        options=list(OP_DESCRIPTIONS.keys()),
        help="Choose which Callas-equivalent operation to run",
        label_visibility="collapsed"
    )

    # Operation description card
    st.markdown(f"""
    <div style="background:rgba(59,130,246,0.08); border:1px solid rgba(59,130,246,0.2);
                border-radius:8px; padding:0.75rem; margin:0.75rem 0; font-size:0.8rem; color:#93b4d4; line-height:1.5;">
        {OP_DESCRIPTIONS[operation]}
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── Per-operation options ──────────────────────────────────────────────────
    options = {}

    if operation == "Set TrimBox":
        st.subheader("TrimBox Size")
        preset = st.selectbox("Preset", [
            "Custom",
            "6ft Table Throw (126.5\" × 84\")",
            "10ft Canopy (122\" × 86.25\")",
            "10ft Tent Crop (118\" × 86.25\")",
        ])
        presets = {
            "6ft Table Throw (126.5\" × 84\")":   (126.5, 84.0),
            "10ft Canopy (122\" × 86.25\")":       (122.0, 86.25),
            "10ft Tent Crop (118\" × 86.25\")":    (118.0, 86.25),
        }
        if preset in presets:
            options["width_inch"], options["height_inch"] = presets[preset]
            st.info(f"{options['width_inch']}\" × {options['height_inch']}\"")
        else:
            options["width_inch"]  = st.number_input("Width (inches)",  value=126.5, step=0.25)
            options["height_inch"] = st.number_input("Height (inches)", value=84.0,  step=0.25)

    elif operation == "Create Identical Pages":
        options["count"] = st.number_input("Number of pages", min_value=1, max_value=20, value=5)

    elif operation == "Preflight Check":
        options["black_target"] = st.selectbox("Black ink target", ["100k", "75x3"])

    st.divider()
    st.markdown("**Poppler path**")
    poppler_path = st.text_input(
        "Poppler bin folder",
        value=ws.POPPLER_BIN,
        help="Path to Poppler bin folder containing pdftocairo.exe"
    )
    ws.POPPLER_BIN = poppler_path


# ── Main area ──────────────────────────────────────────────────────────────────
st.markdown('<div style="font-size:0.75rem; color:#7f9bb5; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:0.5rem;">Upload PDF</div>', unsafe_allow_html=True)
uploaded = st.file_uploader(
    "Drop your PDF here or click to browse",
    type=["pdf"],
    help="Upload the PDF file you want to process"
)

if uploaded:
    st.markdown(f"**File:** `{uploaded.name}`  |  **Size:** {uploaded.size / 1024:.1f} KB")

    # Write upload to a temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_in:
        tmp_in.write(uploaded.read())
        input_path = tmp_in.name

    # ── Quick info panel ───────────────────────────────────────────────────────
    with st.expander("📐 Page Info", expanded=True):
        import fitz
        doc = fitz.open(input_path)
        info_cols = st.columns(len(doc) if len(doc) <= 5 else 5)
        for i, page in enumerate(doc):
            if i >= 5:
                st.caption(f"... and {len(doc)-5} more pages")
                break
            mb = page.mediabox
            tb = page.trimbox
            with info_cols[i]:
                st.metric(f"Page {i+1}", f"{mb.width/72:.2f}\" × {mb.height/72:.2f}\"",
                          delta=f"TrimBox: {tb.width/72:.2f}\" × {tb.height/72:.2f}\"" if tb != mb else "No separate TrimBox",
                          delta_color="off")
        doc.close()

    st.divider()

    # ── Run button ─────────────────────────────────────────────────────────────
    run = st.button(f"▶  Run: {operation}", use_container_width=True)

    if run:
        output_path = tempfile.mktemp(suffix=".pdf")

        with st.spinner(f"Running {operation}..."):
            try:
                # ── Dispatch ──────────────────────────────────────────────────
                if operation == "Preflight Check":
                    report = ws.preflight_report(input_path)

                    st.subheader("📋 Preflight Report")

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Pages", report["pages"])
                    col2.metric("Spot Colors", len(report["spot_colors"]))
                    col3.metric("Status", "✅ PASS" if report["pass"] else "❌ FAIL")

                    if report["spot_colors"]:
                        st.markdown("**Spot Colors Found:**")
                        for name, label in report["spot_colors"].items():
                            color = "🔴" if label and "Template" in label else "✂️" if label == "Cut Contour" else "🟡"
                            st.markdown(f"{color} `{name}` — {label}")

                    if report["issues"]:
                        for issue in report["issues"]:
                            st.markdown(f'<div class="issue-box">❌ {issue}</div>', unsafe_allow_html=True)

                    if report["warnings"]:
                        for warn in report["warnings"]:
                            st.markdown(f'<div class="warn-box">⚠️ {warn}</div>', unsafe_allow_html=True)

                    if report["pass"] and not report["warnings"]:
                        st.markdown('<div class="result-box">✅ File passed all preflight checks.</div>', unsafe_allow_html=True)

                    # No output file for preflight-only
                    output_path = None

                elif operation == "Outline Fonts + Clean Metadata":
                    ws.profile_outline_and_clean(input_path, output_path)

                elif operation == "Set TrimBox":
                    ws.set_trimbox_all_pages(
                        input_path, output_path,
                        width_inch=options["width_inch"],
                        height_inch=options["height_inch"]
                    )

                elif operation == "Set MediaBox to Origin":
                    ws.set_mediabox_to_origin(input_path, output_path)

                elif operation == "Create Identical Pages":
                    ws.create_identical_pages(input_path, output_path,
                                               count=int(options["count"]))

                elif operation == "Remove Bleed":
                    ws.remove_bleed(input_path, output_path)

                elif operation == "Full Finishing — 10ft Tent":
                    ws.profile_10ft_tent(input_path, output_path)

                elif operation == "Full Finishing — 6ft Multi-Page":
                    ws.profile_6ft_multipage(input_path, output_path)

                elif operation == "Full Finishing — SLD 4.2 Top/Bottom":
                    ws.profile_sld_top_bttm(input_path, output_path)

                # ── Success + download ─────────────────────────────────────────
                if output_path and os.path.exists(output_path):
                    st.markdown(f"""
                    <div style="background:rgba(34,197,94,0.1); border:1px solid rgba(34,197,94,0.3);
                                border-radius:10px; padding:1rem 1.25rem; margin:1rem 0;
                                display:flex; align-items:center; gap:0.75rem;">
                        <div style="font-size:1.5rem;">✅</div>
                        <div>
                            <div style="color:#22c55e; font-weight:700; font-size:0.95rem;">Processing Complete</div>
                            <div style="color:#7f9bb5; font-size:0.8rem; margin-top:2px;">{operation} applied successfully</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Show output page info
                    with st.expander("📐 Output Page Info"):
                        doc_out = fitz.open(output_path)
                        out_cols = st.columns(min(len(doc_out), 5))
                        for i, page in enumerate(doc_out):
                            if i >= 5:
                                break
                            mb = page.mediabox
                            tb = page.trimbox
                            with out_cols[i]:
                                st.metric(f"Page {i+1}",
                                          f"{mb.width/72:.2f}\" × {mb.height/72:.2f}\"",
                                          delta=f"Trim: {tb.width/72:.2f}\" × {tb.height/72:.2f}\"",
                                          delta_color="off")
                        doc_out.close()

                    # Download button
                    out_name = Path(uploaded.name).stem + f"_{operation.replace(' ','_').replace('—','').strip()}.pdf"
                    with open(output_path, "rb") as f:
                        st.download_button(
                            label=f"⬇️  Download {out_name}",
                            data=f.read(),
                            file_name=out_name,
                            mime="application/pdf",
                            use_container_width=True,
                        )

            except Exception as e:
                st.markdown(f'<div class="issue-box">❌ Error: {e}</div>',
                            unsafe_allow_html=True)

            finally:
                # Clean up temp input
                try:
                    os.unlink(input_path)
                except Exception:
                    pass

else:
    st.markdown("""
    <div style="background:rgba(59,130,246,0.06); border:1px solid rgba(59,130,246,0.15);
                border-radius:12px; padding:1.5rem 1.75rem; margin-top:0.5rem;">
        <div style="color:#3b82f6; font-size:0.72rem; text-transform:uppercase; letter-spacing:0.1em; font-weight:700; margin-bottom:1rem;">
            Available Operations
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.6rem;">
            <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:0.65rem 0.9rem;">
                <div style="color:#e2e8f0; font-weight:600; font-size:0.85rem;">Preflight Check</div>
                <div style="color:#4a6080; font-size:0.75rem; margin-top:2px;">Detect template spot colors &amp; font issues</div>
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:0.65rem 0.9rem;">
                <div style="color:#e2e8f0; font-weight:600; font-size:0.85rem;">Outline Fonts + Clean Metadata</div>
                <div style="color:#4a6080; font-size:0.75rem; margin-top:2px;">Convert fonts to curves, strip private data</div>
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:0.65rem 0.9rem;">
                <div style="color:#e2e8f0; font-weight:600; font-size:0.85rem;">Set TrimBox</div>
                <div style="color:#4a6080; font-size:0.75rem; margin-top:2px;">Apply trim dimensions with product presets</div>
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:0.65rem 0.9rem;">
                <div style="color:#e2e8f0; font-weight:600; font-size:0.85rem;">Set MediaBox to Origin</div>
                <div style="color:#4a6080; font-size:0.75rem; margin-top:2px;">Normalize page position to 0,0</div>
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:0.65rem 0.9rem;">
                <div style="color:#e2e8f0; font-weight:600; font-size:0.85rem;">Create Identical Pages</div>
                <div style="color:#4a6080; font-size:0.75rem; margin-top:2px;">Duplicate to N-up for gang printing</div>
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:8px; padding:0.65rem 0.9rem;">
                <div style="color:#e2e8f0; font-weight:600; font-size:0.85rem;">Full Finishing Profiles</div>
                <div style="color:#4a6080; font-size:0.75rem; margin-top:2px;">Multi-step pipelines matching your KFPX profiles</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:3rem; padding-top:1rem; border-top:1px solid rgba(255,255,255,0.06);
            display:flex; justify-content:space-between; align-items:center;">
    <div style="color:#2a3a52; font-size:0.72rem;">CallasFlow · WS Display · Built with PyMuPDF + Poppler</div>
    <div style="color:#2a3a52; font-size:0.72rem;">v1.0</div>
</div>
""", unsafe_allow_html=True)
