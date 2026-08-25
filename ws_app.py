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
    page_title="WS Display PDF Tools",
    page_icon="🖨️",
    layout="wide",
)

# ── Styles ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stButton>button {
        background-color: #1a3c6e;
        color: white;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
    }
    .stButton>button:hover { background-color: #254f91; }
    .result-box {
        background: #e8f4e8;
        border-left: 4px solid #2e7d32;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    .issue-box {
        background: #fdecea;
        border-left: 4px solid #c62828;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    .warn-box {
        background: #fff8e1;
        border-left: 4px solid #f9a825;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
    .info-box {
        background: #e3f2fd;
        border-left: 4px solid #1565c0;
        padding: 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([1, 6])
with col_title:
    st.title("🖨️ WS Display PDF Tools")
    st.caption("Automated PDF finishing, preflight, and preparation")

st.divider()

# ── Sidebar — Operation Selector ───────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Operation")

    operation = st.selectbox(
        "Select profile",
        options=[
            "Preflight Check",
            "Outline Fonts + Clean Metadata",
            "Set TrimBox",
            "Set MediaBox to Origin",
            "Create Identical Pages",
            "Remove Bleed",
            "Full Finishing — 10ft Tent",
            "Full Finishing — 6ft Multi-Page",
        ],
        help="Choose which Callas-equivalent operation to run"
    )

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
st.subheader("📄 Upload PDF")
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
    run_col, _ = st.columns([2, 5])
    with run_col:
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

                # ── Success + download ─────────────────────────────────────────
                if output_path and os.path.exists(output_path):
                    st.markdown('<div class="result-box">✅ Processing complete.</div>',
                                unsafe_allow_html=True)

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
    <div class="info-box">
    👆 Upload a PDF above to get started.<br><br>
    <strong>Available operations:</strong><br>
    • <strong>Preflight Check</strong> — detect template spot colors, font issues<br>
    • <strong>Outline Fonts + Clean Metadata</strong> — convert fonts to curves, strip private data<br>
    • <strong>Set TrimBox</strong> — apply correct trim dimensions (table throw, canopy, tent presets)<br>
    • <strong>Set MediaBox to Origin</strong> — normalize page position<br>
    • <strong>Create Identical Pages</strong> — duplicate to N-up<br>
    • <strong>Remove Bleed</strong> — set CropBox to TrimBox<br>
    • <strong>Full Finishing profiles</strong> — multi-step pipelines matching your KFPX profiles
    </div>
    """, unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption("WS Display PDF Tools · Built with PyMuPDF + Poppler · Replaces Callas pdfToolbox for core operations")
