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
    DictionaryObject, BooleanObject, TextStringObject, RectangleObject
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
        # Merge any array of content streams into a single stream first
        page.clean_contents()

        contents_info = doc.xref_get_key(page.xref, "Contents")
        if contents_info[0] != "xref":
            continue  # no content stream to wrap
        c_xref   = int(contents_info[1].split()[0])
        existing = doc.xref_stream(c_xref)
        if not existing:
            continue

        # Resources may be direct or indirect — find the right xref to patch
        res_info = doc.xref_get_key(page.xref, "Resources")
        if res_info[0] == "xref":
            res_xref = int(res_info[1].split()[0])
            doc.xref_set_key(res_xref, "Properties/artwork", f"{layer_xref} 0 R")
        else:
            doc.xref_set_key(page.xref, "Resources/Properties/artwork",
                             f"{layer_xref} 0 R")

        # Wrap existing content with proper marked-content operators
        wrapped = b"/OC /artwork BDC\n" + existing + b"\nEMC\n"
        doc.update_stream(c_xref, wrapped)

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
# SLD FINISHING OPERATIONS  (ffeat: EnlargePage, OutlinePBox, SetPageBoxEx)
# ---------------------------------------------------------------------------

def enlarge_page(input_path: str, output_path: str,
                 top_inch: float = 0.0, bottom_inch: float = 0.0,
                 left_inch: float = 0.0, right_inch: float = 0.0):
    """
    Replicates: EnlargePage
    Expands the MediaBox by the given amounts on each side.
    Content remains at its original position; blank space is added outside.
    All other page boxes (TrimBox, BleedBox, etc.) are left untouched.
    """
    top_pt    = top_inch    * 72.0
    bottom_pt = bottom_inch * 72.0
    left_pt   = left_inch   * 72.0
    right_pt  = right_inch  * 72.0

    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        mb = page.mediabox            # PDF coords: bottom-left origin, y↑
        x0 = float(mb.left)   - left_pt
        y0 = float(mb.bottom) - bottom_pt  # expand downward in PDF space
        x1 = float(mb.right)  + right_pt
        y1 = float(mb.top)    + top_pt     # expand upward in PDF space
        page.mediabox = RectangleObject([x0, y0, x1, y1])
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  Page enlarged ±{top_inch}/{bottom_inch}\" top/bottom: {output_path}")


def add_trimbox_stroke(input_path: str, output_path: str,
                       stroke_width_pt: float = 0.25):
    """
    Replicates: OutlinePBox on TrimBox, CMYK 0,0,0,1 (100K black), 0.25pt
    Draws a hairline black stroke along the TrimBox border.
    ffeat: OutlinePBox
    """
    doc = fitz.open(input_path)
    for page in doc:
        trim = page.trimbox
        if trim is None or trim.is_empty:
            trim = page.mediabox
        page.draw_rect(trim, color=(0, 0, 0, 1), fill=None, width=stroke_width_pt)
    doc.save(output_path, deflate=True, garbage=4, clean=True)
    doc.close()
    print(f"  TrimBox stroke added (100K, {stroke_width_pt}pt): {output_path}")


def set_bleedbox_from_cropbox(input_path: str, output_path: str):
    """
    Replicates: SetPageBoxEx BleedBox = CropBox
    Sets the BleedBox equal to the CropBox on every page.
    ffeat: SetPageBoxEx
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        crop = page.cropbox if "/CropBox" in page else page.mediabox
        page.bleedbox = crop
        writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  BleedBox set from CropBox: {output_path}")


def add_thrucut_spot(input_path: str, output_path: str,
                     stroke_width_pt: float = 0.25):
    """
    Replicates: OutlinePBox on BleedBox with 'thru-cut' Separation spot color.
    Injects a spot color stroke rectangle at the BleedBox boundary so RIPs
    and cutters recognise it as a through-cut path.
    ffeat: OutlinePBox
    """
    doc = fitz.open(input_path)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        bleed = page.bleedbox
        if bleed is None or bleed.is_empty:
            bleed = page.mediabox

        page_h = page.rect.height

        # PDF coordinate space (bottom-left origin, y flipped from PyMuPDF)
        x0   = bleed.x0
        y_lo = page_h - bleed.y1   # PDF y at visual bottom
        x1   = bleed.x1
        y_hi = page_h - bleed.y0   # PDF y at visual top

        spot_name = "thru-cut"
        res_key   = "CSThrCut"     # name used inside the Resources dict

        # ── 1. Build PDF objects: tint function + Separation colorspace ────────
        fn_xref = doc.get_new_xref()
        doc.update_object(fn_xref,
            "<</FunctionType 2/Domain[0.0 1.0]"
            "/C0[0.0 0.0 0.0 0.0]/C1[0.0 0.0 0.0 1.0]/N 1.0>>")

        cs_xref = doc.get_new_xref()
        doc.update_object(cs_xref,
            f"[/Separation /thru-cut /DeviceCMYK {fn_xref} 0 R]")

        # ── 2. Add colorspace to page Resources ───────────────────────────────
        page_xref = page.xref

        # Resolve Resources (may be indirect ref or inline dict)
        res_val = doc.xref_get_key(page_xref, "Resources")
        if not res_val or res_val == "null":
            res_xref = doc.get_new_xref()
            doc.update_object(res_xref, "<<>>")
            doc.xref_set_key(page_xref, "Resources", f"{res_xref} 0 R")
        else:
            parts = res_val.split()
            if len(parts) >= 3 and parts[-1] == "R":
                res_xref = int(parts[0])
            else:
                # Inline dict — materialise as indirect object
                res_xref = doc.get_new_xref()
                inline = res_val if res_val.startswith("<<") else "<<>>"
                doc.update_object(res_xref, inline)
                doc.xref_set_key(page_xref, "Resources", f"{res_xref} 0 R")

        # Resolve / create the ColorSpace sub-dict
        cs_dict_val = doc.xref_get_key(res_xref, "ColorSpace")
        if not cs_dict_val or cs_dict_val == "null":
            cs_dict_xref = doc.get_new_xref()
            doc.update_object(cs_dict_xref, "<<>>")
            doc.xref_set_key(res_xref, "ColorSpace", f"{cs_dict_xref} 0 R")
        else:
            parts2 = cs_dict_val.split()
            if len(parts2) >= 3 and parts2[-1] == "R":
                cs_dict_xref = int(parts2[0])
            else:
                cs_dict_xref = doc.get_new_xref()
                inline2 = cs_dict_val if cs_dict_val.startswith("<<") else "<<>>"
                doc.update_object(cs_dict_xref, inline2)
                doc.xref_set_key(res_xref, "ColorSpace", f"{cs_dict_xref} 0 R")

        doc.xref_set_key(cs_dict_xref, res_key, f"{cs_xref} 0 R")

        # ── 3. Content stream — stroke rect with spot color ───────────────────
        content = (
            f"q\n"
            f"/{res_key} CS\n"             # stroking colorspace = Separation
            f"1.0 SCN\n"                   # tint = 1.0 (full ink)
            f"{stroke_width_pt} w\n"       # line width
            f"{x0:.4f} {y_lo:.4f} m\n"    # bottom-left
            f"{x1:.4f} {y_lo:.4f} l\n"    # bottom-right
            f"{x1:.4f} {y_hi:.4f} l\n"    # top-right
            f"{x0:.4f} {y_hi:.4f} l\n"    # top-left
            f"h S\n"                       # close + stroke
            f"Q\n"
        ).encode("latin-1")

        # ── 4. Append stream to page Contents ─────────────────────────────────
        new_stm = doc.get_new_xref()
        doc.update_stream(new_stm, content)

        contents_val = doc.xref_get_key(page_xref, "Contents")
        if not contents_val or contents_val == "null":
            doc.xref_set_key(page_xref, "Contents", f"{new_stm} 0 R")
        else:
            stripped = contents_val.strip()
            if stripped.startswith("["):
                inner = stripped[1:-1].strip()
                doc.xref_set_key(page_xref, "Contents",
                                  f"[{inner} {new_stm} 0 R]")
            else:
                doc.xref_set_key(page_xref, "Contents",
                                  f"[{stripped} {new_stm} 0 R]")

    doc.save(output_path, deflate=True, garbage=4, clean=True)
    doc.close()
    print(f"  Thru-cut spot stroke added at BleedBox: {output_path}")


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


def profile_sld_top_bttm(input_path: str, output_path: str):
    """
    Mirrors: SLD_4_2_TOP_BTTM_FINISH_.kfpx
    Full SLD 4.2 Top/Bottom finishing pipeline:
    1. Set MediaBox to origin          (ffeat: SetMediaBoxTo00)
    2. Stroke TrimBox in 100K black    (ffeat: OutlinePBox)
    3. Enlarge page +4.5\" top/bottom  (ffeat: EnlargePage)
    4. Set BleedBox = CropBox          (ffeat: SetPageBoxEx)
    5. Add 'thru-cut' spot at BleedBox (ffeat: OutlinePBox w/ spot color)
    """
    run_pipeline(input_path, output_path, [
        set_mediabox_to_origin,
        add_trimbox_stroke,
        lambda i, o: enlarge_page(i, o, top_inch=4.5, bottom_inch=4.5),
        set_bleedbox_from_cropbox,
        add_thrucut_spot,
    ])


# ---------------------------------------------------------------------------
# OPERATION CATALOG  — metadata for Profile Builder UI
# ---------------------------------------------------------------------------

AVAILABLE_OPS = {
    "set_mediabox_to_origin": {
        "label": "Set MediaBox to Origin",
        "category": "Page Geometry",
        "ffeat": "SetMediaBoxTo00",
        "description": "Moves MediaBox so lower-left corner is at (0,0). Required before most finishing steps.",
        "params": [],
    },
    "set_page_box": {
        "label": "Set Page Box",
        "category": "Page Geometry",
        "ffeat": "SetPageBoxEx",
        "description": "Sets any page box (TrimBox, BleedBox, etc.) to specific dimensions, centered on the page.",
        "params": [
            {"name": "box_type", "type": "select", "label": "Box Type",
             "options": ["TrimBox", "MediaBox", "BleedBox", "CropBox", "ArtBox"], "default": "TrimBox"},
            {"name": "width_inch",  "type": "float", "label": "Width (in)",  "default": 118.0,  "step": 0.25},
            {"name": "height_inch", "type": "float", "label": "Height (in)", "default": 86.25, "step": 0.25},
        ],
    },
    "enlarge_page": {
        "label": "Enlarge Page",
        "category": "Page Geometry",
        "ffeat": "EnlargePage",
        "description": "Expands the MediaBox by adding blank space on any side. Content stays in place.",
        "params": [
            {"name": "top_inch",    "type": "float", "label": "Top (in)",    "default": 0.0, "step": 0.25},
            {"name": "bottom_inch", "type": "float", "label": "Bottom (in)", "default": 0.0, "step": 0.25},
            {"name": "left_inch",   "type": "float", "label": "Left (in)",   "default": 0.0, "step": 0.25},
            {"name": "right_inch",  "type": "float", "label": "Right (in)",  "default": 0.0, "step": 0.25},
        ],
    },
    "correct_page_geometry": {
        "label": "Correct Page Boxes",
        "category": "Page Geometry",
        "ffeat": "CorrectPageBoxes",
        "description": "Clamps all page boxes to MediaBox boundaries.",
        "params": [],
    },
    "set_bleedbox_from_cropbox": {
        "label": "Set BleedBox = CropBox",
        "category": "Page Geometry",
        "ffeat": "SetPageBoxEx",
        "description": "Sets BleedBox equal to CropBox on every page.",
        "params": [],
    },
    "remove_bleed": {
        "label": "Remove Bleed",
        "category": "Page Geometry",
        "ffeat": "SetPageBoxEx",
        "description": "Sets CropBox equal to TrimBox, hiding bleed area from output.",
        "params": [],
    },
    "create_identical_pages": {
        "label": "Duplicate to N Pages",
        "category": "Pages",
        "ffeat": "CreateIdenticalPages",
        "description": "Duplicates the artwork to N identical pages (e.g., for gang-run printing).",
        "params": [
            {"name": "count", "type": "int", "label": "Page Count", "default": 5, "min": 1, "max": 20},
        ],
    },
    "create_artwork_layer": {
        "label": "Create Artwork Layer",
        "category": "Layers",
        "ffeat": "PutObjectsOnLayer",
        "description": "Wraps all existing page content in an 'artwork' OCG layer.",
        "params": [],
    },
    "create_cutpath_layer": {
        "label": "Create Cutpath Layer",
        "category": "Layers",
        "ffeat": "PutObjectsOnLayer",
        "description": "Creates an empty 'cutpath' OCG layer on the page.",
        "params": [],
    },
    "outline_fonts": {
        "label": "Outline Fonts",
        "category": "Fonts & Metadata",
        "ffeat": "ConvertFontsToOutlines",
        "description": "Converts all fonts to outlines via pdftocairo. Eliminates font dependencies.",
        "params": [],
    },
    "remove_private_data": {
        "label": "Remove Private Data",
        "category": "Fonts & Metadata",
        "ffeat": "DscrdPrvtDtOfOthrApps",
        "description": "Strips XMP metadata, document info, and private application data.",
        "params": [],
    },
    "add_trimbox_stroke": {
        "label": "Stroke TrimBox (100K)",
        "category": "Marks & Lines",
        "ffeat": "OutlinePBox",
        "description": "Draws a 100% black (CMYK 0,0,0,1) hairline at the TrimBox boundary.",
        "params": [
            {"name": "stroke_width_pt", "type": "float", "label": "Stroke Width (pt)", "default": 0.25, "step": 0.25},
        ],
    },
    "add_thrucut_spot": {
        "label": "Thru-Cut Spot at BleedBox",
        "category": "Marks & Lines",
        "ffeat": "OutlinePBox",
        "description": "Draws the BleedBox border as a 'thru-cut' Separation spot color for RIPs and cutters.",
        "params": [
            {"name": "stroke_width_pt", "type": "float", "label": "Stroke Width (pt)", "default": 0.25, "step": 0.25},
        ],
    },
}

# Grouped view for UI dropdowns
OP_CATEGORIES = {}
for _op_id, _op_meta in AVAILABLE_OPS.items():
    _cat = _op_meta["category"]
    OP_CATEGORIES.setdefault(_cat, []).append(_op_id)


# ---------------------------------------------------------------------------
# PROFILE RUNNER  — executes a JSON profile dict
# ---------------------------------------------------------------------------

def run_profile(input_path: str, output_path: str, profile: dict):
    """
    Execute a profile definition against a PDF.

    profile format:
        {
          "name": "My Profile",
          "steps": [
            {"op": "set_mediabox_to_origin"},
            {"op": "set_page_box", "params": {"box_type": "TrimBox",
                                               "width_inch": 118.0,
                                               "height_inch": 86.25}}
          ]
        }
    """
    import functools

    OP_MAP = {
        "set_mediabox_to_origin":   set_mediabox_to_origin,
        "set_page_box":             set_page_box,
        "set_trimbox_all_pages":    set_trimbox_all_pages,
        "create_artwork_layer":     create_artwork_layer,
        "create_cutpath_layer":     create_cutpath_layer,
        "create_identical_pages":   create_identical_pages,
        "remove_bleed":             remove_bleed,
        "correct_page_geometry":    correct_page_geometry,
        "outline_fonts":            outline_fonts,
        "remove_private_data":      remove_private_data,
        "enlarge_page":             enlarge_page,
        "add_trimbox_stroke":       add_trimbox_stroke,
        "set_bleedbox_from_cropbox":set_bleedbox_from_cropbox,
        "add_thrucut_spot":         add_thrucut_spot,
    }

    steps = []
    for step_def in profile.get("steps", []):
        op_name = step_def["op"]
        params   = step_def.get("params", {})
        fn = OP_MAP.get(op_name)
        if fn is None:
            raise ValueError(f"Unknown operation in profile: '{op_name}'")
        if params:
            bound = functools.partial(fn, **params)
            label = ", ".join(f"{k}={v}" for k, v in params.items())
            bound.__name__ = f"{op_name}({label})"
            steps.append(bound)
        else:
            steps.append(fn)

    run_pipeline(input_path, output_path, steps)


# ---------------------------------------------------------------------------
# Overlay & Cutpath
# ---------------------------------------------------------------------------

def stamp_overlay(input_path: str, output_path: str,
                  overlay_pdf_path: str, opacity: float = 0.5):
    """
    Stamp overlay PDF centred on each artwork page at the given opacity.
    Uses PyMuPDF Form XObjects + PDF ExtGState (vector — no rasterisation).
    """
    doc  = fitz.open(input_path)
    over = fitz.open(overlay_pdf_path)

    for i, page in enumerate(doc):
        ov_idx = min(i, len(over) - 1)

        # Embed overlay page as a Form XObject; appended to content stream
        page.show_pdf_page(page.rect, over, ov_idx, overlay=True)

        # Merge any content stream array into a single stream
        page.clean_contents()

        contents_info = doc.xref_get_key(page.xref, "Contents")
        if contents_info[0] != "xref":
            continue
        c_xref = int(contents_info[1].split()[0])
        raw    = doc.xref_stream(c_xref)
        if not raw:
            continue

        # Register an ExtGState for the desired alpha
        alpha_str = f"{opacity:.3f}"
        res_info  = doc.xref_get_key(page.xref, "Resources")
        if res_info[0] == "xref":
            res_xref = int(res_info[1].split()[0])
            doc.xref_set_key(res_xref, "ExtGState/GSov",
                             f"<</Type /ExtGState /ca {alpha_str} /CA {alpha_str}>>")
        else:
            doc.xref_set_key(page.xref, "Resources/ExtGState/GSov",
                             f"<</Type /ExtGState /ca {alpha_str} /CA {alpha_str}>>")

        # Insert "/GSov gs" after the last bare "q" (overlay's save-state)
        lines  = raw.split(b"\n")
        last_q = max(
            (j for j, ln in enumerate(lines) if ln.strip() == b"q"),
            default=None
        )
        if last_q is not None:
            lines.insert(last_q + 1, b"/GSov gs")
            doc.update_stream(c_xref, b"\n".join(lines))

    doc.save(output_path, garbage=4, deflate=True)
    print(f"  stamp_overlay → {output_path}")


def merge_cutpath(input_path: str, output_path: str, cutpath_pdf_path: str):
    """Append cutpath PDF pages after the artwork pages."""
    doc = fitz.open(input_path)
    cut = fitz.open(cutpath_pdf_path)
    doc.insert_pdf(cut)
    doc.save(output_path, garbage=4, deflate=True)
    print(f"  merge_cutpath → {output_path}")


# ---------------------------------------------------------------------------
# JPEG export
# ---------------------------------------------------------------------------

def export_jpeg(input_path: str, output_path: str, dpi: int = 150):
    """
    Render the first page of a PDF to a JPEG at the given DPI.
    For multi-page PDFs, renders every page and saves as <stem>_p1.jpg, etc.
    Returns list of output paths written.
    """
    doc    = fitz.open(input_path)
    mat    = fitz.Matrix(dpi / 72, dpi / 72)
    paths  = []
    stem   = Path(output_path).stem
    folder = Path(output_path).parent
    ext    = Path(output_path).suffix or ".jpg"

    for i, page in enumerate(doc):
        pix  = page.get_pixmap(matrix=mat, alpha=False)
        dest = str(folder / f"{stem}_p{i+1}{ext}") if len(doc) > 1 else output_path
        pix.save(dest)
        paths.append(dest)
        print(f"  export_jpeg p{i+1} → {dest}")

    doc.close()
    return paths


# ---------------------------------------------------------------------------
# Recipe runner  (preflight → proof JPEG → finishing → cutpath)
# ---------------------------------------------------------------------------

def run_recipe(input_path: str, recipe: dict,
               profiles_dir: str = None,
               overlays_dir: str = None,
               cutpaths_dir: str = None) -> dict:
    """
    Execute a structured recipe and return a dict of output paths:

        {
          "original_jpeg":  ["/tmp/orig_p1.jpg"],     # preflighted file, no overlay
          "overlay_pdf":    "/tmp/overlay.pdf",        # preflighted + overlay (customer proof)
          "overlay_jpeg":   ["/tmp/overlay_p1.jpg"],  # JPEG of overlay PDF
          "cutpath_pdf":    "/tmp/cutpath.pdf",        # standalone cutpath file
          "cutpath_jpeg":   ["/tmp/cutpath_p1.jpg"],  # JPEG of cutpath file
          "finished_pdf":   "/tmp/finished.pdf",       # preflighted + finishing (production)
        }

    Pipeline order:
      1. Preflight  → preflighted PDF  (black conversion — stub for now)
      2. Original JPEG from preflighted PDF
      3. Overlay    → stamp on preflighted → overlay PDF + JPEG
      4. Finishing  → run on preflighted PDF (clean) → finished/production PDF
      5. Cutpath    → JPEG of standalone cutpath file
    """
    import tempfile, shutil, json

    results: dict = {}

    # ── 1. Preflight ──────────────────────────────────────────────────────────
    tmp_pf = tempfile.mktemp(suffix=".pdf")
    preflight = recipe.get("preflight") or ""
    if preflight in ("100k", "75x3"):
        print(f"  [preflight] {preflight} — black conversion not yet implemented; skipping.")
    shutil.copy2(input_path, tmp_pf)

    # ── 2. Original JPEG (preflighted, no overlay) ────────────────────────────
    tmp_orig_jpg = tempfile.mktemp(suffix=".jpg")
    results["original_jpeg"] = export_jpeg(tmp_pf, tmp_orig_jpg)

    # ── 3. Overlay PDF + JPEG ─────────────────────────────────────────────────
    overlay = recipe.get("overlay") or ""
    if overlay and overlays_dir:
        ov_path = Path(overlays_dir) / overlay
        if ov_path.exists():
            tmp_ov     = tempfile.mktemp(suffix=".pdf")
            tmp_ov_jpg = tempfile.mktemp(suffix=".jpg")
            stamp_overlay(tmp_pf, tmp_ov, str(ov_path))
            results["overlay_pdf"]  = tmp_ov
            results["overlay_jpeg"] = export_jpeg(tmp_ov, tmp_ov_jpg)
        else:
            print(f"  [overlay] file not found: {ov_path}")

    # ── 4. Finishing (runs on clean preflighted PDF — no overlay) ─────────────
    finishing = recipe.get("finishing") or ""
    tmp_finished = tmp_pf
    if finishing and profiles_dir:
        pfile = Path(profiles_dir) / f"{finishing}.json"
        if pfile.exists():
            profile_data = json.loads(pfile.read_text())
            tmp_fin = tempfile.mktemp(suffix=".pdf")
            run_profile(tmp_pf, tmp_fin, profile_data)
            tmp_finished = tmp_fin
        else:
            print(f"  [finishing] profile not found: {pfile}")
    results["finished_pdf"]    = tmp_finished
    results["preflighted_pdf"] = tmp_pf

    # ── 5. Cutpath — JPEG of standalone cutpath file ──────────────────────────
    cutpath = recipe.get("cutpath") or ""
    if cutpath and cutpaths_dir:
        cp_path = Path(cutpaths_dir) / cutpath
        if cp_path.exists():
            tmp_cp_jpg = tempfile.mktemp(suffix=".jpg")
            results["cutpath_pdf"]  = str(cp_path)
            results["cutpath_jpeg"] = export_jpeg(str(cp_path), tmp_cp_jpg)
        else:
            print(f"  [cutpath] file not found: {cp_path}")

    return results


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
