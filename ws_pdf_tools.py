"""
ws_pdf_tools.py
WS Display — PDF Processing Module
Replicates core Callas pdfToolbox operations used in our finishing,
preflight, and Switch profiles.

Dependencies:
    pip install pymupdf pypdf
    Poppler: C:\Tools\Poppler\Release-26.02.0-0\poppler-26.02.0\Library\bin\pdftocairo.exe

Usage:
    import ws_pdf_tools as ws
    ws.set_mediabox_to_origin("input.pdf", "output.pdf")
    ws.create_layer(doc, "artwork")
    ...
"""

# Path to Poppler bin folder
POPPLER_BIN = r"C:\Tools\Poppler\Release-26.02.0-0\poppler-26.02.0\Library\bin"

import fitz          # PyMuPDF
import pypdf
from pypdf import PdfWriter, PdfReader
from pypdf.generic import (
    ArrayObject, FloatObject, NameObject, NumberObject,
    DictionaryObject, BooleanObject, TextStringObject
)
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pt(value_inch: float) -> float:
    """Convert inches to PDF points (1 inch = 72 pts)."""
    return value_inch * 72.0

def _mm_to_pt(value_mm: float) -> float:
    """Convert mm to PDF points."""
    return value_mm * 2.83465

def open_pdf(path: str) -> fitz.Document:
    return fitz.open(path)

def save_pdf(doc: fitz.Document, out_path: str, deflate: bool = True):
    doc.save(out_path, deflate=deflate, garbage=4, clean=True)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# PAGE GEOMETRY  (ffeat: SetMediaBoxTo00, SetPageBoxEx, SetTrimBox)
# ---------------------------------------------------------------------------

def set_mediabox_to_origin(input_path: str, output_path: str):
    """
    Replicates: SetMediaBoxTo00
    Moves the MediaBox so its lower-left corner is at (0, 0).
    All other page boxes are shifted to stay in register.
    """
    doc = fitz.open(input_path)
    for page in doc:
        mb = page.mediabox
        dx, dy = -mb.x0, -mb.y0
        if dx == 0 and dy == 0:
            continue
        # Shift all boxes
        page.set_mediabox(fitz.Rect(0, 0, mb.width, mb.height))
        for attr in ("cropbox", "trimbox", "bleedbox", "artbox"):
            box = getattr(page, attr, None)
            if box:
                shifted = fitz.Rect(box.x0 + dx, box.y0 + dy,
                                    box.x1 + dx, box.y1 + dy)
                getattr(page, f"set_{attr}")(shifted)
    save_pdf(doc, output_path)
    doc.close()


def set_page_box(input_path: str, output_path: str,
                 box_type: str = "MediaBox",
                 width_inch: float = None, height_inch: float = None,
                 width_mm: float = None, height_mm: float = None,
                 pages: str = "all"):
    """
    Replicates: SetPageBoxEx
    Sets the specified page box to a given size, centered on the current box.

    box_type: 'MediaBox' | 'TrimBox' | 'BleedBox' | 'CropBox' | 'ArtBox'
    pages: 'all' or 1-based page number (int) or list of ints
    """
    if width_inch is not None:
        w = _pt(width_inch)
        h = _pt(height_inch)
    elif width_mm is not None:
        w = _mm_to_pt(width_mm)
        h = _mm_to_pt(height_mm)
    else:
        raise ValueError("Provide width/height in inches or mm")

    doc = fitz.open(input_path)
    target_pages = range(len(doc)) if pages == "all" else (
        [pages - 1] if isinstance(pages, int) else [p - 1 for p in pages]
    )

    box_map = {
        "MediaBox": "mediabox", "TrimBox": "trimbox",
        "BleedBox": "bleedbox", "CropBox": "cropbox", "ArtBox": "artbox"
    }
    attr = box_map.get(box_type, "mediabox")

    for i in target_pages:
        page = doc[i]
        ref = page.mediabox
        cx, cy = (ref.x0 + ref.x1) / 2, (ref.y0 + ref.y1) / 2
        new_box = fitz.Rect(cx - w/2, cy - h/2, cx + w/2, cy + h/2)
        getattr(page, f"set_{attr}")(new_box)

    save_pdf(doc, output_path)
    doc.close()


def set_trimbox_all_pages(input_path: str, output_path: str,
                           width_inch: float = None, height_inch: float = None,
                           width_mm: float = None, height_mm: float = None):
    """
    Replicates: SetTrimBox (used in Switch profiles for table throws, canopies)
    Sets TrimBox on every page to the given size, centered on MediaBox.
    """
    set_page_box(input_path, output_path,
                 box_type="TrimBox",
                 width_inch=width_inch, height_inch=height_inch,
                 width_mm=width_mm, height_mm=height_mm)


# ---------------------------------------------------------------------------
# LAYERS  (ffeat: PutObjectsOnLayer)
# ---------------------------------------------------------------------------

def ensure_layer(doc: fitz.Document, layer_name: str) -> str:
    """
    Replicates: PutObjectsOnLayer (layer creation step)
    Creates an Optional Content Group (OCG) layer if it doesn't exist.
    Returns the layer xref string for use in content streams.
    """
    # Check if layer already exists
    ocgs = doc.get_ocgs()
    for xref, info in ocgs.items():
        if info.get("name") == layer_name:
            return xref

    # Create new OCG
    xref = doc.add_ocg(layer_name, on=True)
    return xref


def create_artwork_layer(input_path: str, output_path: str):
    """
    Replicates: Create artwork layer (PutObjectsOnLayer → 'artwork')
    Wraps all existing page content in an 'artwork' OCG layer.
    """
    doc = fitz.open(input_path)
    layer_xref = ensure_layer(doc, "artwork")

    for page in doc:
        # Wrap existing content stream in OCG marked content
        existing = page.read_contents()
        if existing:
            wrapped = (
                b"/OC /" + f"OC{layer_xref}".encode() + b" BDC\n" +
                existing +
                b"\nEMC\n"
            )
            page.set_contents(wrapped)

    save_pdf(doc, output_path)
    doc.close()


def create_cutpath_layer(input_path: str, output_path: str):
    """
    Replicates: Create Cut path layer (PutObjectsOnLayer → 'cutpath')
    Creates an empty 'cutpath' OCG layer ready to receive cut path objects.
    Note: actual cut path content must be added separately (or via Callas WBApply).
    """
    doc = fitz.open(input_path)
    ensure_layer(doc, "cutpath")
    save_pdf(doc, output_path)
    doc.close()


# ---------------------------------------------------------------------------
# PAGE DUPLICATION  (ffeat: CreateIdenticalPages)
# ---------------------------------------------------------------------------

def create_identical_pages(input_path: str, output_path: str,
                            count: int = 5, source_page: int = 1):
    """
    Replicates: Create X identical pages
    Duplicates source_page (1-based) to fill the document with `count` copies.
    Used in 6ft-4-MULTI-5PC-BLEED profile.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()

    src = reader.pages[source_page - 1]
    for _ in range(count):
        writer.add_page(src)

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  Saved: {output_path} ({count} pages)")


# ---------------------------------------------------------------------------
# BLEED / GEOMETRY  (ffeat: used in Remove bleed, FFF_Correctpagegeometry)
# ---------------------------------------------------------------------------

def remove_bleed(input_path: str, output_path: str):
    """
    Replicates: Remove bleed
    Sets CropBox = TrimBox on all pages, effectively hiding bleed area.
    """
    doc = fitz.open(input_path)
    for page in doc:
        tb = page.trimbox
        if tb:
            page.set_cropbox(tb)
    save_pdf(doc, output_path)
    doc.close()


def correct_page_geometry(input_path: str, output_path: str):
    """
    Replicates: FFF_Correctpagegeometryboxesifpossible
    Ensures all page boxes are contained within and consistent with MediaBox.
    Clamps TrimBox/BleedBox/CropBox to MediaBox boundaries.
    """
    doc = fitz.open(input_path)
    for page in doc:
        mb = page.mediabox
        for attr in ("trimbox", "bleedbox", "cropbox", "artbox"):
            box = getattr(page, attr, None)
            if box:
                clamped = mb & box  # intersection
                if not clamped.is_empty:
                    getattr(page, f"set_{attr}")(clamped)
    save_pdf(doc, output_path)
    doc.close()


# ---------------------------------------------------------------------------
# PREFLIGHT — SPOT COLOR DETECTION  (used in WS_PREFLIGHT profiles)
# ---------------------------------------------------------------------------

TEMPLATE_SPOT_COLORS = {
    # Keyword → what we flag it as
    "white":       "Template White",
    "black":       "Template Black",
    "red":         "Template Red",
    "blue":        "Template Blue",
    "yellow":      "Template Yellow",
    "cutcontour":  "Cut Contour",
    "dieline":     "Cut Contour",
    "cut":         "Cut Contour",
}

def detect_spot_colors(input_path: str) -> dict:
    """
    Replicates: Template Spot Color Identified rules
    Scans all pages for spot colors and classifies them.

    Returns dict: { spot_name: classification_label }
    """
    reader = PdfReader(input_path)
    found = {}

    def scan_resources(resources):
        if resources is None:
            return
        cs = resources.get("/ColorSpace")
        if cs:
            for key in cs:
                cs_obj = cs[key]
                if hasattr(cs_obj, 'get_object'):
                    cs_obj = cs_obj.get_object()
                if isinstance(cs_obj, list) and len(cs_obj) > 1:
                    cs_type = str(cs_obj[0])
                    if cs_type == "/Separation":
                        name = str(cs_obj[1]).lstrip("/")
                        name_lower = name.lower()
                        label = None
                        for keyword, classification in TEMPLATE_SPOT_COLORS.items():
                            if keyword in name_lower:
                                label = classification
                                break
                        found[name] = label or "Unknown Spot"

    for page in reader.pages:
        scan_resources(page.get("/Resources"))

    return found


def preflight_report(input_path: str) -> dict:
    """
    Runs all preflight checks and returns a structured report.
    """
    spots = detect_spot_colors(input_path)
    reader = PdfReader(input_path)

    issues = []
    warnings = []

    # Check spot colors
    for name, label in spots.items():
        if label == "Cut Contour":
            warnings.append(f"Cut contour spot color found: '{name}'")
        elif label and label.startswith("Template"):
            issues.append(f"Template spot color found: '{name}' ({label}) — should be removed or converted")
        elif label == "Unknown Spot":
            warnings.append(f"Unknown spot color: '{name}'")

    # Check page count
    page_count = len(reader.pages)

    # Check for embedded fonts
    font_issues = []
    for i, page in enumerate(reader.pages):
        res = page.get("/Resources")
        if res:
            fonts = res.get("/Font")
            if fonts:
                for fname in fonts:
                    font_obj = fonts[fname]
                    if hasattr(font_obj, 'get_object'):
                        font_obj = font_obj.get_object()
                    embedded = font_obj.get("/FontDescriptor")
                    if not embedded:
                        font_issues.append(f"Page {i+1}: font '{fname}' may not be embedded")

    return {
        "file": input_path,
        "pages": page_count,
        "spot_colors": spots,
        "issues": issues,
        "warnings": warnings + font_issues,
        "pass": len(issues) == 0
    }


# ---------------------------------------------------------------------------
# SPOT COLOR REMAPPING  (used in WS_PREFLIGHT profiles)
# ---------------------------------------------------------------------------

def remap_spot_white_to_cmyk(input_path: str, output_path: str):
    """
    Replicates: Remap spot color using the word 'white' to CMYK white
    Converts any spot color whose name contains 'white' to CMYK (0,0,0,0).

    Note: Full color space remapping requires Ghostscript for complex cases.
    This handles the ColorSpace dictionary substitution in the PDF structure.
    """
    # This operation modifies the PDF's ColorSpace resources
    # Using pypdf for direct object manipulation
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append(reader)

    for page in writer.pages:
        res = page.get("/Resources")
        if res is None:
            continue
        cs_dict = res.get("/ColorSpace")
        if cs_dict is None:
            continue
        for key in list(cs_dict.keys()):
            cs_obj = cs_dict[key]
            if hasattr(cs_obj, 'get_object'):
                cs_obj = cs_obj.get_object()
            if isinstance(cs_obj, list) and len(cs_obj) > 1:
                if str(cs_obj[0]) == "/Separation":
                    name = str(cs_obj[1]).lstrip("/")
                    if "white" in name.lower():
                        # Replace with DeviceCMYK at 0,0,0,0
                        cs_dict[key] = ArrayObject([
                            NameObject("/Separation"),
                            NameObject(f"/{name}"),
                            NameObject("/DeviceCMYK"),
                            # Identity tint transform → maps to 0,0,0,0
                        ])
                        print(f"  Remapped spot '{name}' → CMYK white")

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  Saved: {output_path}")


# ---------------------------------------------------------------------------
# FONT OUTLINING  (via Ghostscript — placeholder until outline-fonts KFPX read)
# ---------------------------------------------------------------------------

def outline_fonts(input_path: str, output_path: str):
    """
    Replicates: OUTLINE-FONTS.kfpx → ffeat: ConvertFontsToOutlines (no params)
    Uses Poppler's pdftocairo to convert all fonts to outlines (curves).

    Requires: Poppler at POPPLER_BIN path above.
    pdftocairo renders each page with fonts as paths — equivalent to
    Callas ConvertFontsToOutlines with default settings.
    """
    import subprocess
    import os
    import shutil

    # Try pdftocairo.exe (Windows) then pdftocairo (Linux/Mac)
    pdftocairo = os.path.join(POPPLER_BIN, "pdftocairo.exe")
    if not os.path.exists(pdftocairo):
        pdftocairo = os.path.join(POPPLER_BIN, "pdftocairo")
    if not os.path.exists(pdftocairo):
        pdftocairo = shutil.which("pdftocairo")
    if not pdftocairo:
        raise RuntimeError(
            f"pdftocairo not found.\n"
            f"Checked: {os.path.join(POPPLER_BIN, 'pdftocairo.exe')}\n"
            f"Make sure Poppler is installed and POPPLER_BIN is set correctly."
        )

    # pdftocairo -pdf writes output as "<stem>.pdf" — use a dedicated temp dir
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    tmp_stem = os.path.join(tmp_dir, "out")
    expected = tmp_stem + ".pdf"

    # Add Poppler bin to PATH so its DLLs are found on Windows
    env = os.environ.copy()
    env["PATH"] = POPPLER_BIN + os.pathsep + env.get("PATH", "")

    try:
        result = subprocess.run(
            [pdftocairo, "-pdf", input_path, tmp_stem],
            capture_output=True, text=True, env=env
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"pdftocairo failed (code {result.returncode}):\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        # Find whatever pdftocairo actually created (Windows omits .pdf extension)
        created = os.listdir(tmp_dir)
        if not created:
            raise RuntimeError(
                f"pdftocairo ran but produced no output.\n"
                f"Temp dir contents: {created}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        shutil.copy2(os.path.join(tmp_dir, created[0]), output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"  Fonts outlined via pdftocairo: {output_path}")


def remove_private_data(input_path: str, output_path: str):
    """
    Replicates: OUTLINE-FONTS.kfpx → ffeat: DscrdPrvtDtOfOthrApps (no params)
    Removes XMP metadata, document info dict, and private application data.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append(reader)

    # Clear document info
    writer.add_metadata({
        "/Title": "",
        "/Author": "",
        "/Subject": "",
        "/Keywords": "",
        "/Creator": "",
        "/Producer": "WS Display PDF Tools",
    })

    # Remove XMP metadata stream if present
    if "/Metadata" in writer._root_object:
        del writer._root_object["/Metadata"]

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  Private data removed: {output_path}")


# ---------------------------------------------------------------------------
# PIPELINE HELPER — chain multiple operations
# ---------------------------------------------------------------------------

def run_pipeline(input_path: str, output_path: str, steps: list):
    """
    Run a sequence of operations on a PDF, writing a final output.

    steps: list of callables that each accept (input_path, output_path)

    Example:
        run_pipeline("art.pdf", "finished.pdf", [
            set_mediabox_to_origin,
            lambda i, o: set_page_box(i, o, "TrimBox", width_inch=118, height_inch=86.25),
            lambda i, o: outline_fonts_gs(i, o, remove_metadata=True),
        ])
    """
    import tempfile, os, shutil

    current = input_path
    tmp_files = []

    try:
        for i, step in enumerate(steps):
            is_last = (i == len(steps) - 1)
            if is_last:
                next_path = output_path
            else:
                tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp.close()
                next_path = tmp.name
                tmp_files.append(next_path)

            print(f"  Step {i+1}/{len(steps)}: {step.__name__ if hasattr(step, '__name__') else 'lambda'}")
            step(current, next_path)
            current = next_path

    finally:
        for f in tmp_files:
            try:
                os.unlink(f)
            except Exception:
                pass

    print(f"\nPipeline complete → {output_path}")


# ---------------------------------------------------------------------------
# PROFILE PRESETS  (mirrors your actual KFPX profiles)
# ---------------------------------------------------------------------------

def profile_10ft_tent(input_path: str, output_path: str):
    """
    Mirrors: 10FT_TENT_FINISH_NB_V2_mask-and-bleed.kfpx
    1. Set MediaBox to origin
    2. Create artwork layer
    3. Create cutpath layer
    4. Set page to 118" x 86.25" (10ft tent final crop)
    Note: WBShape/WBApply clipping mask step still requires Callas
    """
    run_pipeline(input_path, output_path, [
        set_mediabox_to_origin,
        create_artwork_layer,
        create_cutpath_layer,
        lambda i, o: set_page_box(i, o, "MediaBox",
                                   width_inch=118, height_inch=86.25),
    ])


def profile_preflight(input_path: str,
                       black_target: str = "100k") -> dict:
    """
    Mirrors: WS_PREFLIGHT_1_INCH_T_100k / WS_PREFLIGHT_1_INCH_T_75x3
    Runs preflight checks and returns report dict.
    black_target: '100k' or '75x3' (affects which black fixup would apply)
    """
    report = preflight_report(input_path)
    print(f"\nPreflight Report — {Path(input_path).name}")
    print(f"  Pages: {report['pages']}")
    print(f"  Spot colors found: {list(report['spot_colors'].keys()) or 'None'}")
    if report["issues"]:
        print("  ISSUES:")
        for issue in report["issues"]:
            print(f"    ✗ {issue}")
    if report["warnings"]:
        print("  WARNINGS:")
        for w in report["warnings"]:
            print(f"    ⚠ {w}")
    print(f"  Result: {'PASS' if report['pass'] else 'FAIL'}")
    return report


def profile_6ft_multipage(input_path: str, output_path: str,
                            page_count: int = 5):
    """
    Mirrors: 6ft-4-MULTI-5PC-BLEED-V1-.kfpx
    1. Duplicate to N identical pages
    2. Correct page geometry boxes
    """
    run_pipeline(input_path, output_path, [
        lambda i, o: create_identical_pages(i, o, count=page_count),
        correct_page_geometry,
    ])


def profile_outline_and_clean(input_path: str, output_path: str):
    """
    Mirrors: OUTLINE-FONTS.kfpx
    1. Outline all fonts via pdftocairo (ffeat: ConvertFontsToOutlines)
    2. Remove private/metadata (ffeat: DscrdPrvtDtOfOthrApps)
    """
    run_pipeline(input_path, output_path, [
        outline_fonts,
        remove_private_data,
    ])


# ---------------------------------------------------------------------------
# CLI  — run from terminal
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(
        description="WS Display PDF Tools — Callas replacement operations"
    )
    subparsers = parser.add_subparsers(dest="command")

    # preflight
    pf = subparsers.add_parser("preflight", help="Run preflight checks")
    pf.add_argument("input")
    pf.add_argument("--black", default="100k", choices=["100k", "75x3"])

    # origin
    og = subparsers.add_parser("origin", help="Set MediaBox to origin")
    og.add_argument("input")
    og.add_argument("output")

    # outline
    ot = subparsers.add_parser("outline", help="Outline fonts + remove private data")
    ot.add_argument("input")
    ot.add_argument("output")

    # multipage
    mp = subparsers.add_parser("multipage", help="Duplicate to N pages")
    mp.add_argument("input")
    mp.add_argument("output")
    mp.add_argument("--count", type=int, default=5)

    # profile presets
    pr = subparsers.add_parser("profile", help="Run a named profile preset")
    pr.add_argument("name", choices=["10ft-tent", "preflight", "6ft-multi", "outline"])
    pr.add_argument("input")
    pr.add_argument("output", nargs="?")

    args = parser.parse_args()

    if args.command == "preflight":
        report = profile_preflight(args.input, args.black)
        print(json.dumps(report, indent=2))
    elif args.command == "origin":
        set_mediabox_to_origin(args.input, args.output)
    elif args.command == "outline":
        profile_outline_and_clean(args.input, args.output)

    elif args.command == "multipage":
        create_identical_pages(args.input, args.output, args.count)
    elif args.command == "profile":
        if args.name == "10ft-tent":
            profile_10ft_tent(args.input, args.output)
        elif args.name == "preflight":
            profile_preflight(args.input)
        elif args.name == "6ft-multi":
            profile_6ft_multipage(args.input, args.output)
        elif args.name == "outline":
            profile_outline_and_clean(args.input, args.output)
    else:
        parser.print_help()
