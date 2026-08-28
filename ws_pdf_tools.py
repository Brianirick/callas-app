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
                 left_inch: float = 0.0, right_inch: float = 0.0,
                 update_trimbox: bool = True):
    """
    Replicates: EnlargePage
    Expands the MediaBox by the given amounts on each side.
    Content remains at its original position; blank space is added outside.

    update_trimbox=True (default): TrimBox and BleedBox are updated to match
      the new MediaBox — use this when adding canvas that is part of the
      finished print size (pole pockets, top/bottom canvas, etc.).
    update_trimbox=False: TrimBox stays at its original position — use when
      adding bleed outside an existing TrimBox.
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
        new_rect = RectangleObject([x0, y0, x1, y1])
        page.mediabox = new_rect
        if update_trimbox:
            page.cropbox  = new_rect   # CropBox controls display in Acrobat
            page.trimbox  = new_rect
            page.bleedbox = new_rect
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
        "description": "Expands the MediaBox by adding blank space on any side. Enable 'Update TrimBox' when adding canvas (pole pockets, etc.); disable when adding bleed outside an existing TrimBox.",
        "params": [
            {"name": "top_inch",       "type": "float", "label": "Top (in)",           "default": 0.0,  "step": 0.25},
            {"name": "bottom_inch",    "type": "float", "label": "Bottom (in)",         "default": 0.0,  "step": 0.25},
            {"name": "left_inch",      "type": "float", "label": "Left (in)",           "default": 0.0,  "step": 0.25},
            {"name": "right_inch",     "type": "float", "label": "Right (in)",          "default": 0.0,  "step": 0.25},
            {"name": "update_trimbox", "type": "bool",  "label": "Update TrimBox/BleedBox to new size", "default": True},
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
    "adjust_black_vectors": {
        "label": "Adjust Black Vectors",
        "category": "Colors",
        "description": "Converts black/near-black vector colors to a WS Display standard target CMYK value.",
        "params": [
            {"name": "target", "type": "select", "label": "Target Black",
             "options": ["60-50-50-100", "75-75-75-100"], "default": "60-50-50-100"},
        ],
    },
    "remap_white_spot_colors": {
        "label": "Remap White Spot → CMYK 0,0,0,0",
        "category": "Colors",
        "ffeat": "MapSpotColors",
        "description": "Finds Separation spot colors whose name contains 'white' (case-insensitive) and remaps their tint function to output CMYK (0,0,0,0).",
        "params": [],
    },
    "convert_lab_to_cmyk": {
        "label": "Convert Lab to CMYK",
        "category": "Colors",
        "ffeat": "CCSettings",
        "description": "Converts CIE Lab colorspace objects (vectors, text, images) to DeviceCMYK. Uses approximate D50 Lab→XYZ→sRGB→CMYK conversion.",
        "params": [],
    },
}

# Grouped view for UI dropdowns
OP_CATEGORIES = {}
for _op_id, _op_meta in AVAILABLE_OPS.items():
    _cat = _op_meta["category"]
    OP_CATEGORIES.setdefault(_cat, []).append(_op_id)


# ---------------------------------------------------------------------------
# CHECK FUNCTIONS  — inspect PDF and return pass/fail results (no file change)
# ---------------------------------------------------------------------------

def check_page_size(input_path: str,
                    width_inch: float = None, height_inch: float = None,
                    box: str = "TrimBox", tolerance_inch: float = 0.1) -> list:
    """
    Check that each page's box matches expected dimensions (±tolerance).
    Returns list of {page, passed, message} dicts.
    """
    doc = fitz.open(input_path)
    results = []
    for i, page in enumerate(doc):
        rect = getattr(page, box.lower(), None) or page.mediabox
        w, h = rect.width / 72, rect.height / 72
        ok   = True
        msgs = [f"Page {i+1}: {box} = {w:.3f}\" × {h:.3f}\""]
        if width_inch is not None and abs(w - width_inch) > tolerance_inch:
            ok = False
            msgs.append(f"width mismatch — expected {width_inch:.3f}\"")
        if height_inch is not None and abs(h - height_inch) > tolerance_inch:
            ok = False
            msgs.append(f"height mismatch — expected {height_inch:.3f}\"")
        results.append({"page": i+1, "passed": ok, "message": " | ".join(msgs)})
    doc.close()
    return results


def check_has_trimbox(input_path: str) -> list:
    """Check that every page has a TrimBox set."""
    doc  = fitz.open(input_path)
    results = []
    for i, page in enumerate(doc):
        mb = page.mediabox
        tb = page.trimbox
        ok = (tb != mb) and (tb.width > 0)
        results.append({
            "page": i+1, "passed": ok,
            "message": f"Page {i+1}: TrimBox {'present' if ok else 'MISSING'} "
                       f"({tb.width/72:.3f}\" × {tb.height/72:.3f}\")"
        })
    doc.close()
    return results


def check_bleed(input_path: str, min_bleed_inch: float = 0.125) -> list:
    """Check that BleedBox extends at least min_bleed beyond TrimBox on all sides."""
    doc = fitz.open(input_path)
    results = []
    for i, page in enumerate(doc):
        tb = page.trimbox
        bb = page.bleedbox
        min_pt = min_bleed_inch * 72
        ok = (bb.x0 <= tb.x0 - min_pt and bb.y0 <= tb.y0 - min_pt and
              bb.x1 >= tb.x1 + min_pt and bb.y1 >= tb.y1 + min_pt)
        bleed_l = (tb.x0 - bb.x0) / 72
        bleed_b = (tb.y0 - bb.y0) / 72
        bleed_r = (bb.x1 - tb.x1) / 72
        bleed_t = (bb.y1 - tb.y1) / 72
        results.append({
            "page": i+1, "passed": ok,
            "message": f"Page {i+1}: bleed L={bleed_l:.3f}\" B={bleed_b:.3f}\" "
                       f"R={bleed_r:.3f}\" T={bleed_t:.3f}\" "
                       f"(min {min_bleed_inch}\")"
        })
    doc.close()
    return results


def check_spot_colors(input_path: str, allowed: list = None) -> list:
    """
    Check for spot colors. Pass if only allowed spot colors are present
    (or allowed=None to just list what's found without failing).
    """
    report = preflight_report(input_path)
    spots  = list(report.get("spot_colors", {}).keys())
    if allowed is None:
        passed = True
        msg = f"Spot colors found: {', '.join(spots) if spots else 'None'}"
    else:
        unexpected = [s for s in spots if s not in allowed]
        passed = len(unexpected) == 0
        msg = (f"Spot colors OK: {spots}" if passed
               else f"Unexpected spot colors: {unexpected}")
    return [{"page": "all", "passed": passed, "message": msg}]


# Catalog of available checks for the Profile Builder UI
AVAILABLE_CHECKS = {
    "check_page_size": {
        "label": "Check Page Size",
        "category": "Page Geometry",
        "description": "Verifies each page's box matches expected W × H (±tolerance).",
        "params": [
            {"name": "box",          "type": "select", "label": "Box Type",
             "options": ["TrimBox","MediaBox","BleedBox","CropBox"], "default": "TrimBox"},
            {"name": "width_inch",   "type": "float",  "label": "Expected Width (in)",  "default": 0.0, "step": 0.25},
            {"name": "height_inch",  "type": "float",  "label": "Expected Height (in)", "default": 0.0, "step": 0.25},
            {"name": "tolerance_inch","type": "float", "label": "Tolerance (in)",       "default": 0.1, "step": 0.01},
        ],
    },
    "check_has_trimbox": {
        "label": "Check TrimBox Present",
        "category": "Page Geometry",
        "description": "Fails if any page is missing a TrimBox.",
        "params": [],
    },
    "check_bleed": {
        "label": "Check Bleed",
        "category": "Page Geometry",
        "description": "Verifies BleedBox extends beyond TrimBox by at least the specified amount.",
        "params": [
            {"name": "min_bleed_inch", "type": "float", "label": "Min Bleed (in)", "default": 0.125, "step": 0.0625},
        ],
    },
    "check_spot_colors": {
        "label": "Check Spot Colors",
        "category": "Colors",
        "description": "Lists spot colors found. Leave 'Allowed' blank to just report without failing.",
        "params": [],
    },
}


# ---------------------------------------------------------------------------
# PROFILE RUNNER  — executes a JSON profile dict
# ---------------------------------------------------------------------------

def run_profile(input_path: str, output_path: str, profile: dict) -> dict:
    """
    Execute a profile definition against a PDF.

    Supports two step types:
      Fixup:  {"op": "set_mediabox_to_origin"}
      Check:  {"op": "check_page_size", "type": "check",
               "params": {"width_inch": 10.0, "height_inch": 8.0}}

    Returns dict:
      {
        "output_path":   str,
        "check_results": [  # one entry per check step
          {"step": int, "op": str, "label": str, "results": [...]}
        ]
      }
    """
    import functools

    FIXUP_MAP = {
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
        "adjust_black_vectors":     adjust_black_vectors,
        "remap_white_spot_colors":  remap_white_spot_colors,
        "convert_lab_to_cmyk":      convert_lab_to_cmyk,
    }

    CHECK_MAP = {
        "check_page_size":    check_page_size,
        "check_has_trimbox":  check_has_trimbox,
        "check_bleed":        check_bleed,
        "check_spot_colors":  check_spot_colors,
    }

    fixup_steps    = []   # (fn,) for run_pipeline
    check_schedule = []   # (step_idx, op_name, params) to run after fixups
    check_results  = []

    for i, step_def in enumerate(profile.get("steps", [])):
        op_name   = step_def["op"]
        params    = step_def.get("params", {})
        step_type = step_def.get("type", "fixup")

        if step_type == "check":
            fn = CHECK_MAP.get(op_name)
            if fn is None:
                raise ValueError(f"Unknown check operation: '{op_name}'")
            check_schedule.append((i, op_name, params, fn))
        else:
            fn = FIXUP_MAP.get(op_name)
            if fn is None:
                raise ValueError(f"Unknown fixup operation: '{op_name}'")
            if params:
                bound = functools.partial(fn, **params)
                label = ", ".join(f"{k}={v}" for k, v in params.items())
                bound.__name__ = f"{op_name}({label})"
                fixup_steps.append(bound)
            else:
                fixup_steps.append(fn)

    # Run fixups
    if fixup_steps:
        run_pipeline(input_path, output_path, fixup_steps)
    else:
        import shutil
        shutil.copy2(input_path, output_path)

    # Run checks against the output (post-fixup state)
    check_path = output_path if fixup_steps else input_path
    for step_idx, op_name, params, fn in check_schedule:
        results = fn(check_path, **params) if params else fn(check_path)
        meta = AVAILABLE_CHECKS.get(op_name, {})
        check_results.append({
            "step":    step_idx,
            "op":      op_name,
            "label":   meta.get("label", op_name),
            "results": results,
        })

    return {
        "output_path":   output_path,
        "check_results": check_results,
    }


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
# BLACK VECTOR COLOR ADJUSTMENT
# ---------------------------------------------------------------------------

# Source colors in PDF 0-1 scale from WS Display Callas mapping tables.
# Both targets (60-50-50-100 and 75-75-75-100) share the same source list.
_BLACK_SOURCES_CMYK = [
    (0.75,   0.75,   0.75,   1.00),    # 75 75 75 100
    (1.00,   1.00,   1.00,   1.00),    # 100 100 100 100
    (0.60,   0.40,   0.40,   1.00),    # 60 40 40 100
    (0.75,   0.67,   0.67,   0.99),    # 75 67 67 99
    (0.6982, 0.6745, 0.6386, 0.7394),  # 69.82 67.45 63.86 73.94
    (0.75,   0.679,  0.671,  0.901),   # 75 67.9 67.1 90.1
    (0.30,   0.30,   0.30,   1.00),    # 30 30 30 100
    (0.7461, 0.7458, 0.6680, 0.8984),  # 74.61 74.58 66.8 89.84
    (0.40,   0.30,   0.20,   1.00),    # 40 30 20 100
    (0.40,   0.30,   0.30,   1.00),    # 40 30 30 100
    (0.50,   0.50,   0.50,   1.00),    # 50 50 50 100
    (0.7342, 0.68,   0.657,  0.8575),  # 73.42 68 65.7 85.75
    (0.75,   0.68,   0.67,   0.90),    # 75 68 67 90
    (0.40,   0.40,   0.40,   1.00),    # 40 40 40 100
    (0.60,   0.60,   0.60,   1.00),    # 60 60 60 100
    (0.80,   0.80,   0.80,   1.00),    # 80 80 80 100
    (0.50,   0.40,   0.40,   1.00),    # 50 40 40 100
    (0.749,  0.678,  0.671,  0.902),   # 74.9 67.8 67.1 90.2
    (0.00,   0.00,   0.00,   1.00),    # 0 0 0 100 — pure K
]
_BLACK_SOURCES_RGB = [(0.0, 0.0, 0.0)]  # RGB 0 0 0
_BLACK_MATCH_TOL   = 0.005              # ±0.5% per channel

_PREFLIGHT_TARGETS = {
    "60-50-50-100": (0.60, 0.50, 0.50, 1.00),
    "75-75-75-100": (0.75, 0.75, 0.75, 1.00),
    "100k":         (0.60, 0.50, 0.50, 1.00),  # legacy alias
    "75x3":         (0.75, 0.75, 0.75, 1.00),  # legacy alias
}


def _bv_cmyk_matches(c, m, y, k):
    t = _BLACK_MATCH_TOL
    return any(abs(c-sc)<=t and abs(m-sm)<=t and abs(y-sy)<=t and abs(k-sk)<=t
               for sc, sm, sy, sk in _BLACK_SOURCES_CMYK)


def _bv_rgb_matches(r, g, b):
    t = _BLACK_MATCH_TOL
    return any(abs(r-sr)<=t and abs(g-sg)<=t and abs(b-sb)<=t
               for sr, sg, sb in _BLACK_SOURCES_RGB)


def _bv_fmt(v: float) -> bytes:
    s = f"{v:.5f}".rstrip("0").rstrip(".")
    return (s or "0").encode()


import re as _re
_BV_NUM = _re.compile(rb'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_BV_WS  = _re.compile(rb'[ \t\r\n]+')
_BV_OP  = _re.compile(rb"[A-Za-z'\"*]+")


def _bv_tokenize(data: bytes) -> list:
    """Tokenize a PDF content stream → [(type, raw_bytes), ...]."""
    tokens, i, n = [], 0, len(data)
    while i < n:
        ch = data[i:i+1]
        m = _BV_WS.match(data, i)
        if m:
            tokens.append(('ws', m.group())); i = m.end(); continue
        if ch == b'%':                         # comment → treat as ws
            j = i
            while j < n and data[j:j+1] not in (b'\r', b'\n'): j += 1
            tokens.append(('ws', data[i:j])); i = j; continue
        if ch == b'(':                          # string literal
            depth, j = 1, i + 1
            while j < n and depth > 0:
                c2 = data[j:j+1]
                if c2 == b'\\': j += 2
                elif c2 == b'(': depth += 1; j += 1
                elif c2 == b')': depth -= 1; j += 1
                else: j += 1
            tokens.append(('str', data[i:j])); i = j; continue
        if ch == b'<' and data[i+1:i+2] != b'<':  # hex string
            j = data.index(b'>', i) + 1
            tokens.append(('str', data[i:j])); i = j; continue
        if data[i:i+2] in (b'<<', b'>>'):
            tokens.append(('other', data[i:i+2])); i += 2; continue
        if ch in b'[]{}/':
            if ch == b'/':
                j = i + 1
                while j < n and data[j:j+1] not in b' \t\r\n/()<>[]{}%': j += 1
                tokens.append(('name', data[i:j])); i = j; continue
            tokens.append(('other', ch)); i += 1; continue
        if ch in b'0123456789.-+':
            m = _BV_NUM.match(data, i)
            if m:
                tokens.append(('num', m.group())); i = m.end(); continue
        m = _BV_OP.match(data, i)
        if m:
            tokens.append(('op', m.group())); i = m.end(); continue
        tokens.append(('other', ch)); i += 1
    return tokens


def _bv_recolor(data: bytes, tgt: tuple) -> bytes:
    """Replace matching black color operators with target CMYK in a content stream."""
    tc, tm, ty, tk = [_bv_fmt(v) for v in tgt]
    tokens = _bv_tokenize(data)
    out = []
    i = 0
    while i < len(tokens):
        tp, tv = tokens[i]
        if tp == 'op' and tv in (b'k', b'K', b'rg', b'RG', b'g', b'G'):
            need = 4 if tv in (b'k', b'K') else 3 if tv in (b'rg', b'RG') else 1
            # collect last `need` num positions in out[]
            num_pos, j = [], len(out) - 1
            while j >= 0 and len(num_pos) < need:
                if out[j][0] == 'num':   num_pos.insert(0, j)
                elif out[j][0] != 'ws':  break
                j -= 1
            if len(num_pos) == need:
                vals = [float(out[p][1]) for p in num_pos]
                hit = (
                    _bv_cmyk_matches(*vals) if tv in (b'k', b'K') else
                    _bv_rgb_matches(*vals)  if tv in (b'rg', b'RG') else
                    vals[0] <= 0.05
                )
                if hit:
                    cmyk4 = [tc, tm, ty, tk]
                    if tv in (b'k', b'K'):
                        for s, p in enumerate(num_pos): out[p] = ('num', cmyk4[s])
                        out.append(('op', tv))
                    elif tv in (b'rg', b'RG'):
                        for s, p in enumerate(num_pos): out[p] = ('num', cmyk4[s])
                        out += [('ws', b' '), ('num', tk),
                                ('ws', b' '), ('op', b'k' if tv == b'rg' else b'K')]
                    elif tv in (b'g', b'G'):
                        out[num_pos[0]] = ('num', tc)
                        out += [('ws', b' '), ('num', tm),
                                ('ws', b' '), ('num', ty),
                                ('ws', b' '), ('num', tk),
                                ('ws', b' '), ('op', b'k' if tv == b'g' else b'K')]
                    i += 1; continue
        out.append((tp, tv))
        i += 1
    return b''.join(v for _, v in out)


def adjust_black_vectors(input_path: str, output_path: str,
                         target: str = "60-50-50-100") -> None:
    """
    Convert vector black colors to a WS Display standard target.

    target: "60-50-50-100"  →  CMYK 60/50/50/100  (WS Display standard)
            "75-75-75-100"  →  CMYK 75/75/75/100
            "100k" / "75x3" accepted as legacy aliases.

    Only the main page content stream is modified (k, K, rg, RG, g, G operators).
    Raster images are skipped. Form XObjects inside the page are also processed.
    """
    tgt = _PREFLIGHT_TARGETS.get(target, _PREFLIGHT_TARGETS["60-50-50-100"])
    doc = fitz.open(input_path)
    done = set()

    for page in doc:
        page.clean_contents()
        ci = doc.xref_get_key(page.xref, "Contents")
        if ci[0] == "xref":
            c_xref = int(ci[1].split()[0])
            if c_xref not in done:
                raw = doc.xref_stream(c_xref)
                if raw:
                    new = _bv_recolor(raw, tgt)
                    if new != raw:
                        doc.update_stream(c_xref, new)
                done.add(c_xref)
        # Also process Form XObjects in page resources
        try:
            for item in page.get_xobjects():
                xref = item[0]
                if xref in done: continue
                if doc.xref_get_key(xref, "Subtype")[1] == "/Form":
                    raw = doc.xref_stream(xref)
                    if raw:
                        new = _bv_recolor(raw, tgt)
                        if new != raw:
                            doc.update_stream(xref, new)
                done.add(xref)
        except Exception:
            pass

    save_pdf(doc, output_path)
    doc.close()
    print(f"  adjust_black_vectors → {target}: {output_path}")


# ---------------------------------------------------------------------------
# SPOT COLOR REMAP  (ffeat: MapSpotColors)
# ---------------------------------------------------------------------------

import re as _re
_WHITE_SPOT_PAT = _re.compile(r'(?i).*white.*')


def remap_white_spot_colors(input_path: str, output_path: str) -> None:
    """
    Replicates: MapSpotColors "Remap spot color using the word 'white' to CMYK white"
    Finds Separation colorspaces whose name matches (?i).*white.* on any page
    and replaces their tint function with one that always outputs CMYK (0, 0, 0, 0).
    Applies to vector and text objects.
    """
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.clone_reader_document_root(reader)

    def _zero_tint_fn():
        """Type 2 exponential function: tint→[0,0,0,0] for DeviceCMYK."""
        return DictionaryObject({
            NameObject("/FunctionType"): NumberObject(2),
            NameObject("/Domain"):  ArrayObject([FloatObject(0.0), FloatObject(1.0)]),
            NameObject("/C0"):      ArrayObject([FloatObject(0.0)] * 4),
            NameObject("/C1"):      ArrayObject([FloatObject(0.0)] * 4),
            NameObject("/N"):       NumberObject(1),
        })

    remapped = set()

    for page in writer.pages:
        res = page.get("/Resources")
        if not res or "/ColorSpace" not in res:
            continue
        cs_dict = res["/ColorSpace"]
        for key in list(cs_dict.keys()):
            cs_obj = cs_dict[key]
            # Resolve indirect refs
            if hasattr(cs_obj, "get_object"):
                cs_obj = cs_obj.get_object()
            if not isinstance(cs_obj, ArrayObject) or len(cs_obj) < 2:
                continue
            if str(cs_obj[0]) != "/Separation":
                continue
            raw_name = cs_obj[1]
            spot_name = str(raw_name).lstrip("/")
            if not _WHITE_SPOT_PAT.match(spot_name):
                continue
            new_cs = ArrayObject([
                NameObject("/Separation"),
                raw_name,
                NameObject("/DeviceCMYK"),
                _zero_tint_fn(),
            ])
            cs_dict[NameObject(key)] = new_cs
            remapped.add(spot_name)

    with open(output_path, "wb") as f:
        writer.write(f)

    if remapped:
        print(f"  remap_white_spot_colors: remapped {remapped} → CMYK 0,0,0,0")
    else:
        print(f"  remap_white_spot_colors: no white spot colors found")
    print(f"  → {output_path}")


# ---------------------------------------------------------------------------
# LAB → CMYK CONVERSION  (ffeat: CCDestination / CCSettings)
# ---------------------------------------------------------------------------

def _lab_to_cmyk_approx(L: float, a: float, b: float):
    """
    CIE L*a*b* (D50 illuminant) → CMYK.
    Approximation via XYZ → linear sRGB → CMYK (no ICC profile required).
    L in [0,100], a/b in [-128,127].
    Returns (c, m, y, k) each in [0.0, 1.0].
    """
    # Lab → XYZ  (D50 whitepoint: Xn=0.9642, Yn=1.0000, Zn=0.8251)
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    def _f_inv(t):
        return t ** 3 if t > 0.20690 else (t - 16.0 / 116.0) / 7.787

    X = 0.9642 * _f_inv(fx)
    Y = 1.0000 * _f_inv(fy)
    Z = 0.8251 * _f_inv(fz)

    # XYZ (D50) → linear sRGB  (D50-adapted sRGB matrix)
    r_lin =  3.1338561 * X - 1.6168667 * Y - 0.4906146 * Z
    g_lin = -0.9787684 * X + 1.9161415 * Y + 0.0334540 * Z
    b_lin =  0.0719453 * X - 0.2289914 * Y + 1.4052427 * Z

    def _gamma(v):
        v = max(0.0, min(1.0, v))
        return 12.92 * v if v <= 0.0031308 else 1.055 * (v ** (1.0 / 2.4)) - 0.055

    r, g, b_ = _gamma(r_lin), _gamma(g_lin), _gamma(b_lin)

    # sRGB → CMYK
    k = 1.0 - max(r, g, b_)
    if k >= 1.0:
        return 0.0, 0.0, 0.0, 1.0
    inv = 1.0 / (1.0 - k)
    c = max(0.0, min(1.0, (1.0 - r  - k) * inv))
    m = max(0.0, min(1.0, (1.0 - g  - k) * inv))
    y = max(0.0, min(1.0, (1.0 - b_ - k) * inv))
    k = max(0.0, min(1.0, k))
    return c, m, y, k


def _lab_recolor(data: bytes, fill_labs: set, stroke_labs: set) -> bytes:
    """
    Rewrite a PDF content stream, converting Lab fill/stroke colors to CMYK.

    fill_labs  / stroke_labs : sets of b'/Name' bytes for Lab colorspaces active
                               on the current fill / stroke channel.

    Handles:
      /LabName cs  → /DeviceCMYK cs   (fill colorspace switch)
      /LabName CS  → /DeviceCMYK CS   (stroke colorspace switch)
      L a b scn/sc → C M Y K scn/sc  (fill color, 3→4 values)
      L a b SCN/SC → C M Y K SCN/SC  (stroke color, 3→4 values)
    """
    tokens = _bv_tokenize(data)
    out = list(tokens)

    fill_is_lab   = False
    stroke_is_lab = False

    i = 0
    while i < len(out):
        tok_type, tok_raw = out[i]

        if tok_type != 'op':
            i += 1
            continue

        op = tok_raw.strip()

        # ── Colorspace operators ──────────────────────────────────────────────
        if op in (b'cs', b'CS'):
            # Find the preceding name token
            j = i - 1
            while j >= 0 and out[j][0] == 'ws':
                j -= 1
            if j >= 0 and out[j][0] == 'name':
                name_b = out[j][1].strip()
                is_lab = name_b in (fill_labs | stroke_labs)
                if op == b'cs':
                    fill_is_lab = is_lab
                else:
                    stroke_is_lab = is_lab
                if is_lab:
                    out[j] = ('name', b'/DeviceCMYK')
            i += 1
            continue

        # Reset CS tracking on direct colorspace ops
        if op in (b'g', b'rg', b'k'):
            fill_is_lab = False
        elif op in (b'G', b'RG', b'K'):
            stroke_is_lab = False

        # ── Color value operators ─────────────────────────────────────────────
        want_lab = (op in (b'scn', b'sc') and fill_is_lab) or \
                   (op in (b'SCN', b'SC') and stroke_is_lab)

        if want_lab:
            # Scan back for exactly 3 preceding num tokens
            num_pos = []
            j = i - 1
            while j >= 0 and len(num_pos) < 3:
                if out[j][0] == 'num':
                    num_pos.insert(0, j)
                elif out[j][0] != 'ws':
                    break
                j -= 1

            if len(num_pos) == 3:
                try:
                    L_val = float(out[num_pos[0]][1])
                    a_val = float(out[num_pos[1]][1])
                    b_val = float(out[num_pos[2]][1])
                    c, m, y, k = _lab_to_cmyk_approx(L_val, a_val, b_val)
                    out[num_pos[0]] = ('num', _bv_fmt(c))
                    out[num_pos[1]] = ('num', _bv_fmt(m))
                    out[num_pos[2]] = ('num', _bv_fmt(y))
                    # Replace the op token with K-value + space + op
                    out[i] = ('num', _bv_fmt(k))
                    out.insert(i + 1, ('ws', b' '))
                    out.insert(i + 2, ('op', op))
                    i += 3
                    continue
                except (ValueError, IndexError):
                    pass

        i += 1

    return b"".join(raw for _, raw in out)


def convert_lab_to_cmyk(input_path: str, output_path: str) -> None:
    """
    Replicates: CCSettings/CCDestination "Convert LAB to CMYK"
    Finds named Lab colorspaces in each page's resources, converts vector/text
    Lab color operators in content streams to DeviceCMYK equivalents.
    Lab images are also re-encoded to CMYK via PyMuPDF Pixmap conversion.
    """
    # ── Step 1: find Lab colorspace names per page (using pypdf) ─────────────
    reader = PdfReader(input_path)
    page_lab_names: list[set] = []   # one set of b'/Name' per page

    for page in reader.pages:
        labs: set = set()
        res = page.get("/Resources")
        if res:
            cs_dict = res.get("/ColorSpace")
            if cs_dict:
                for key, cs_obj in cs_dict.items():
                    if hasattr(cs_obj, "get_object"):
                        cs_obj = cs_obj.get_object()
                    if isinstance(cs_obj, ArrayObject) and len(cs_obj) >= 1:
                        cs_type = str(cs_obj[0])
                        if cs_type == "/Lab":
                            labs.add(key.encode() if isinstance(key, str) else key)
        page_lab_names.append(labs)

    has_lab = any(page_lab_names)

    # ── Step 2: rewrite content streams (using fitz) ──────────────────────────
    doc = fitz.open(input_path)
    converted_pages = 0

    for page_idx, page in enumerate(doc):
        labs = page_lab_names[page_idx]
        if not labs:
            continue

        page.clean_contents()

        # Main page content stream
        contents_key = doc.xref_get_key(page.xref, "Contents")
        if contents_key[0] != "null":
            # May be single xref or array
            val = contents_key[1]
            if val.startswith("["):
                # Array of streams — collect xrefs
                import re as _re2
                xrefs = [int(x) for x in _re2.findall(r'(\d+)\s+0\s+R', val)]
            else:
                xrefs = [int(val.split()[0])]

            for c_xref in xrefs:
                raw = doc.xref_stream(c_xref)
                if raw:
                    new = _lab_recolor(raw, labs, labs)
                    if new != raw:
                        doc.update_stream(c_xref, new)

        # Form XObjects (best effort)
        try:
            for _name, _type, xref in page.get_xobjects():
                raw = doc.xref_stream(xref)
                if raw:
                    new = _lab_recolor(raw, labs, labs)
                    if new != raw:
                        doc.update_stream(xref, new)
        except Exception:
            pass

        converted_pages += 1

    # ── Step 3: Lab images → CMYK via Pixmap ─────────────────────────────────
    if has_lab:
        cmyk_cs = fitz.Colorspace(fitz.CS_CMYK)
        for page in doc:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.colorspace and pix.colorspace.name == "Lab":
                        pix_cmyk = fitz.Pixmap(cmyk_cs, pix)
                        doc.update_stream(xref, pix_cmyk.tobytes("png"))
                        pix_cmyk = None
                    pix = None
                except Exception:
                    pass

    save_pdf(doc, output_path)
    doc.close()

    if has_lab:
        print(f"  convert_lab_to_cmyk: converted {converted_pages} page(s) → {output_path}")
    else:
        print(f"  convert_lab_to_cmyk: no Lab colorspaces found, file copied")


# ---------------------------------------------------------------------------
# Recipe runner  (preflight → proof JPEG → finishing → cutpath)
# ---------------------------------------------------------------------------

def apply_finishing(input_path: str, output_path: str, finishing: dict) -> None:
    """
    Apply finishing indicators to a PDF proof.

    finishing dict types:
      {"type": "hem_top_bottom",       "top_inch": 1.0,  "bottom_inch": 1.0}
      {"type": "hem_top_bottom_black", "top_inch": 2.5,  "bottom_inch": 2.5}
      {"type": "thru_cut_only"}

    hem_top_bottom:
      - Expands the page by top_inch/bottom_inch to show pole pocket/hem area
      - Draws a dashed black fold line at the original TrimBox edge
      - Draws a magenta thru-cut line at the outer edge

    hem_top_bottom_black:
      - Same as hem_top_bottom but fills the hem bands with a near-black rectangle
        (used on narrow banners with a pre-printed black header/footer)

    thru_cut_only:
      - No enlargement; draws a black TrimBox stroke + magenta outer cut line
    """
    ftype    = finishing.get("type", "")
    top_in   = finishing.get("top_inch", 0.0)
    bot_in   = finishing.get("bottom_inch", 0.0)
    TOP_PT   = top_in * 72.0
    BOT_PT   = bot_in * 72.0

    BLACK     = (0, 0, 0)
    THRU_CUT  = (1, 0, 1)          # magenta = 0C 100M 0Y 0K
    DARK_FILL = (0.05, 0.05, 0.05) # near-black hem fill

    src = fitz.open(input_path)
    dst = fitz.open()

    for pno in range(len(src)):
        src_page = src[pno]
        w = src_page.rect.width
        h = src_page.rect.height

        if ftype in ("hem_top_bottom", "hem_top_bottom_black"):
            new_h    = h + TOP_PT + BOT_PT
            new_page = dst.new_page(width=w, height=new_h)

            # Place original content in the middle zone
            new_page.show_pdf_page(fitz.Rect(0, TOP_PT, w, TOP_PT + h), src, pno)

            # Fill hem bands with dark rectangle (black finish variant)
            if ftype == "hem_top_bottom_black":
                if TOP_PT > 0:
                    new_page.draw_rect(fitz.Rect(0, 0, w, TOP_PT),
                                       color=None, fill=DARK_FILL, overlay=False)
                if BOT_PT > 0:
                    new_page.draw_rect(fitz.Rect(0, TOP_PT + h, w, new_h),
                                       color=None, fill=DARK_FILL, overlay=False)

            # Dashed fold line at top
            if TOP_PT > 0:
                new_page.draw_line(fitz.Point(0, TOP_PT), fitz.Point(w, TOP_PT),
                                   color=BLACK, width=0.75, dashes="[6 4] 0")
            # Dashed fold line at bottom
            if BOT_PT > 0:
                new_page.draw_line(fitz.Point(0, TOP_PT + h), fitz.Point(w, TOP_PT + h),
                                   color=BLACK, width=0.75, dashes="[6 4] 0")

            # Thru-cut line at outer edge
            new_page.draw_rect(fitz.Rect(0.5, 0.5, w - 0.5, new_h - 0.5),
                               color=THRU_CUT, width=0.75)

        elif ftype == "flag_label":
            # Flag finishing: keep original page size.
            # Labels are NOT added here — they are inserted directly onto tmp_finished
            # in run_recipe() AFTER all other stamping, so they render on top of
            # the finishing cutpath's white mask fill.
            new_page = dst.new_page(width=w, height=h)
            new_page.show_pdf_page(fitz.Rect(0, 0, w, h), src, pno)

        elif ftype == "thru_cut_only":
            new_page = dst.new_page(width=w, height=h)
            new_page.show_pdf_page(fitz.Rect(0, 0, w, h), src, pno)
            # Black stroke at TrimBox edge
            new_page.draw_rect(fitz.Rect(0.5, 0.5, w - 0.5, h - 0.5),
                               color=BLACK, width=0.5)
            # Magenta thru-cut at outer edge
            new_page.draw_rect(fitz.Rect(0, 0, w, h),
                               color=THRU_CUT, width=1.0)
        else:
            # Unknown type — pass through unchanged
            new_page = dst.new_page(width=w, height=h)
            new_page.show_pdf_page(fitz.Rect(0, 0, w, h), src, pno)

    dst.save(output_path, deflate=True, garbage=4)
    dst.close()
    src.close()


def run_recipe(input_path: str, recipe: dict,
               profiles_dir: str = None,
               overlays_dir: str = None,
               cutpaths_dir: str = None,
               status_cb=None) -> dict:
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
    def _step(msg):
        print(f"  {msg}")
        if status_cb: status_cb(msg)

    # ── 1. Preflight  (order matches Callas KFPX: white spots → Lab→CMYK → black adj) ──
    tmp_pf   = tempfile.mktemp(suffix=".pdf")
    preflight = recipe.get("preflight") or ""
    if preflight in _PREFLIGHT_TARGETS:
        tmp_a = tempfile.mktemp(suffix=".pdf")
        tmp_b = tempfile.mktemp(suffix=".pdf")
        _step("🎨 Remapping white spot colors…")
        remap_white_spot_colors(input_path, tmp_a)
        _step("🔬 Converting Lab → CMYK…")
        convert_lab_to_cmyk(tmp_a, tmp_b)
        _step(f"⚫ Adjusting vector blacks → {preflight}…")
        adjust_black_vectors(tmp_b, tmp_pf, target=preflight)
    else:
        if preflight:
            _step(f"⚠️ Unknown preflight target '{preflight}', skipping.")
        shutil.copy2(input_path, tmp_pf)

    # ── 1b. Page size check (runs on preflighted file) ───────────────────────
    check_sz = recipe.get("check_size") or {}
    if check_sz and check_sz.get("width_inch") and check_sz.get("height_inch"):
        _step(f"📐 Checking page size {check_sz['width_inch']}\" × {check_sz['height_inch']}\"…")
        results["check_size_results"] = check_page_size(
            tmp_pf,
            width_inch=check_sz["width_inch"],
            height_inch=check_sz["height_inch"],
            tolerance_inch=check_sz.get("tolerance_inch", 0.1),
        )

    # ── 2. Original JPEG (preflighted, no overlay) ────────────────────────────
    _step("🖼 Generating preview JPEG…")
    tmp_orig_jpg = tempfile.mktemp(suffix=".jpg")
    results["original_jpeg"] = export_jpeg(tmp_pf, tmp_orig_jpg)

    # ── 3. Overlay PDF + JPEG ─────────────────────────────────────────────────
    overlay = recipe.get("overlay") or ""
    if overlay and overlays_dir:
        ov_path = Path(overlays_dir) / overlay
        if ov_path.exists():
            _step(f"📄 Stamping overlay: {overlay}…")
            tmp_ov     = tempfile.mktemp(suffix=".pdf")
            tmp_ov_jpg = tempfile.mktemp(suffix=".jpg")
            stamp_overlay(tmp_pf, tmp_ov, str(ov_path))
            results["overlay_pdf"]  = tmp_ov
            results["overlay_jpeg"] = export_jpeg(tmp_ov, tmp_ov_jpg)
        else:
            print(f"  [overlay] file not found: {ov_path}")

    # ── 4. Finishing (runs on clean preflighted PDF — no overlay) ─────────────
    finishing    = recipe.get("finishing") or ""
    tmp_finished = tmp_pf

    # ── Resolve label config ───────────────────────────────────────────────────
    # Labels can come from two places:
    #   (a) flag_label finishing dict  — legacy, all-in-one
    #   (b) top-level "labels" key     — works alongside ANY finishing type
    # Both produce the same stamp; (b) takes precedence when both exist.
    _lbl_cfg = None
    if isinstance(finishing, dict) and finishing.get("type") == "flag_label":
        _lbl_cfg = finishing          # has placeholder, labels[], cutpath
    if recipe.get("labels"):
        _lbl_cfg = recipe["labels"]   # overrides flag_label if both present

    # ── 4a. Stamp finishing cutpath (flag shape mask) BEFORE labels ────────────
    if _lbl_cfg and cutpaths_dir:
        _fin_cp_name = _lbl_cfg.get("cutpath") or ""
        if _fin_cp_name:
            _fin_cp_path = Path(cutpaths_dir) / _fin_cp_name
            if _fin_cp_path.exists():
                _step(f"✂️ Stamping finishing cutpath: {_fin_cp_name}…")
                tmp_pf_with_cp = tempfile.mktemp(suffix=".pdf")
                stamp_overlay(tmp_pf, tmp_pf_with_cp, str(_fin_cp_path), opacity=1.0)
                tmp_pf = tmp_pf_with_cp
            else:
                _step(f"⚠️ Finishing cutpath not found: {_fin_cp_name}")

    if finishing:
        if isinstance(finishing, dict):
            # Native Python finishing (hem, thru-cut, flag_label wrapper, etc.)
            ftype = finishing.get("type", "finishing")
            _step(f"🏷 Applying {ftype}…")
            tmp_fin = tempfile.mktemp(suffix=".pdf")
            apply_finishing(tmp_pf, tmp_fin, finishing)
            tmp_finished = tmp_fin
        elif isinstance(finishing, str) and profiles_dir:
            pfile = Path(profiles_dir) / f"{finishing}.json"
            if pfile.exists():
                profile_data = json.loads(pfile.read_text())
                tmp_fin = tempfile.mktemp(suffix=".pdf")
                run_profile(tmp_pf, tmp_fin, profile_data)
                tmp_finished = tmp_fin
            else:
                print(f"  [finishing] profile not found: {pfile}")

    # ── 4c. Stamp order labels as final overlay (on top of everything) ─────────
    # Stamping last guarantees the labels form XObject is appended after the
    # cutpath's white-fill XObject in the content stream, so text paints on top.
    if _lbl_cfg and _lbl_cfg.get("labels"):
        _step("🏷 Inserting order labels…")
        _fdoc = fitz.open(tmp_finished)
        _lw, _lh = _fdoc[0].rect.width, _fdoc[0].rect.height
        _fdoc.close()
        _lbldoc  = fitz.open()
        _lblpage = _lbldoc.new_page(width=_lw, height=_lh)
        _ltext = _lbl_cfg.get("placeholder", "ORDER #00000")
        for _lbl in _lbl_cfg.get("labels", []):
            _anchor = _lbl.get("anchor", "LowerLeft")
            _lx     = float(_lbl.get("x_pt", 5))
            _ly     = float(_lbl.get("y_pt", 160))
            _lrot   = int(_lbl.get("rotation", 90))
            _lsize  = float(_lbl.get("size", 24))
            if _anchor == "LowerLeft":
                _lpt = fitz.Point(_lx + _lsize, _lh - _ly)
            else:  # LowerRight — x_pt negative means from right edge
                _lpt = fitz.Point(_lw + _lx, _lh - _ly)
            _lblpage.insert_text(_lpt, _ltext, fontsize=_lsize, rotate=_lrot,
                                 color=(0, 0, 0))
        _ltmp_lbl = tempfile.mktemp(suffix=".pdf")
        _lbldoc.save(_ltmp_lbl)
        _lbldoc.close()
        _ltmp = tempfile.mktemp(suffix=".pdf")
        stamp_overlay(tmp_finished, _ltmp, _ltmp_lbl, opacity=1.0)
        tmp_finished = _ltmp

    results["finished_pdf"]    = tmp_finished
    results["preflighted_pdf"] = tmp_pf

    # ── 5. Cutpath — JPEG of standalone cutpath file ──────────────────────────
    cutpath = recipe.get("cutpath") or ""
    if cutpath and cutpaths_dir:
        cp_path = Path(cutpaths_dir) / cutpath
        if cp_path.exists():
            _step(f"✂️ Stamping cutpath: {cutpath}…")
            tmp_cp     = tempfile.mktemp(suffix=".pdf")
            tmp_cp_jpg = tempfile.mktemp(suffix=".jpg")
            stamp_overlay(tmp_pf, tmp_cp, str(cp_path), opacity=1.0)
            results["cutpath_pdf"]  = tmp_cp
            results["cutpath_jpeg"] = export_jpeg(tmp_cp, tmp_cp_jpg)
        else:
            _step(f"⚠️ Cutpath not found: {cutpath}")
    _step("✅ Done!")

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
