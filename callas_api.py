"""
callas_api.py
HTTP API over ws_pdf_tools so quickproof-api can call callas-app instead of
pdftoolbox.exe. One endpoint per pdftoolbox command quickproof-api uses
(see quickproof-api/Helpers/CommandBuilder.cs).

Run with:
    python -m uvicorn callas_api:app --host 0.0.0.0 --port 8000

Environment:
    CALLAS_API_KEY       required; callers send it as the X-Api-Key header
    CALLAS_PROFILES_DIR  recipe JSON folder (default: ./profiles)

Every endpoint takes multipart/form-data with the PDF in `file` and returns
the resulting file. /preflight also returns the report in the
X-Preflight-Report header, shaped like pdftoolbox's finish.json.
"""

import hmac, json, os, shutil, sys, tempfile
from pathlib import Path

# ws_pdf_tools prints "→" etc.; on Windows a redirected stdout is cp1252 and would
# raise UnicodeEncodeError mid-request
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")

import boto3
import fitz
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

import ws_pdf_tools as ws

BASE_DIR     = Path(__file__).parent
PROFILES_DIR = Path(os.environ.get("CALLAS_PROFILES_DIR", BASE_DIR / "profiles"))

# Same bucket/prefix ws_app.py uses for recipe cutpaths
S3_BUCKET         = "quickproof-database-2"
S3_CUTPATH_PREFIX = "Cutpaths-PDF/"
CUTPATHS_DIR      = Path(tempfile.gettempdir()) / "ws_pdf_cache" / "cutpaths"

app = FastAPI(title="callas-app API")


def require_api_key(x_api_key: str = Header(default="")):
    expected = os.environ.get("CALLAS_API_KEY", "")
    if not expected:
        raise HTTPException(500, "CALLAS_API_KEY is not configured")
    if not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(401, "Invalid API key")


def _save_upload(upload: UploadFile, folder: str, name: str) -> str:
    path = os.path.join(folder, name)
    with open(path, "wb") as fh:
        shutil.copyfileobj(upload.file, fh)
    # Customers sometimes send EPS / legacy .ai (even renamed .pdf): Callas skips those,
    # so turn them into a real PDF first. Real PDFs pass through untouched.
    raw = path + ".raw"
    os.replace(path, raw)
    try:
        ws.convert_to_pdf(raw, path)
    except Exception as e:
        os.replace(raw, path)
        raise HTTPException(422, f"Could not read file as PDF/EPS/AI: {e}")
    os.remove(raw)
    return path


def _respond(path: str, workdir: str, media_type: str, headers: dict = None):
    """Stream the file back, then delete the request's temp folder."""
    return FileResponse(path, media_type=media_type, headers=headers,
                        background=BackgroundTask(shutil.rmtree, workdir, True))


def find_recipe(product: str) -> dict | None:
    """Recipe whose name (or file stem) matches the quickproof product name."""
    key = (product or "").strip().lower()
    if not key or not PROFILES_DIR.exists():
        return None
    for p in sorted(PROFILES_DIR.rglob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("type") == "recipe" and key in (str(data.get("name", "")).lower(), p.stem.lower()):
            return data
    return None


def _fetch_cutpath(name: str) -> None:
    """Download a recipe cutpath from S3 into CUTPATHS_DIR (cached)."""
    if not name or (CUTPATHS_DIR / name).exists():
        return
    CUTPATHS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        boto3.client("s3").download_file(S3_BUCKET, S3_CUTPATH_PREFIX + name,
                                         str(CUTPATHS_DIR / name))
    except Exception as e:
        # run_recipe logs "cutpath not found" and continues, same as the Streamlit app
        print(f"[S3 fetch error] {S3_CUTPATH_PREFIX + name}: {e}")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/preflight", dependencies=[Depends(require_api_key)])
def preflight(file: UploadFile = File(...), product: str = Form(...),
              width_in: float | None = Form(None), height_in: float | None = Form(None)):
    """Recipe preflight colour fixes + page-size check (pdftoolbox preflight KFPX)."""
    workdir = tempfile.mkdtemp(prefix="callas_")
    src = _save_upload(file, workdir, "in.pdf")
    out = os.path.join(workdir, "out.pdf")
    errors = []

    try:
        with fitz.open(src) as doc:
            encrypted = bool(doc.needs_pass or doc.is_encrypted)
    except Exception as e:
        encrypted = False
        errors.append(f"Could not open PDF: {e}")

    recipe = find_recipe(product)
    if errors or encrypted:
        shutil.copy2(src, out)
    elif recipe is None:
        errors.append(f"No callas-app recipe for product '{product}'")
        shutil.copy2(src, out)
    else:
        target = recipe.get("preflight") or ""
        if target in ws._PREFLIGHT_TARGETS:
            ws.preflight_colors(src, out, target)
        else:
            shutil.copy2(src, out)

        size = dict(recipe.get("check_size") or {})
        # Product HasVariables dimensions win over the recipe, as with --setvariable
        if width_in and height_in:
            size.update(width_inch=width_in, height_inch=height_in)
        if size.get("width_inch") and size.get("height_inch"):
            results = ws.check_page_size(out, width_inch=size["width_inch"],
                                         height_inch=size["height_inch"],
                                         tolerance_inch=size.get("tolerance_inch", 0.1))
            errors += [r["message"] for r in results if not r["passed"]]

    # Template elements are left in the file and printed, so the customer is warned instead
    # (production KFPX rule "File contains template elements": a document-level warning).
    warnings = []
    if not encrypted:
        try:
            tpl = ws.find_template_spot_names(out)
        except Exception as e:
            tpl = []
            print(f"[template check] failed: {e}")
        if tpl:
            warnings.append("File contains template elements: " + ", ".join(tpl)
                            + " — these areas will print. Remove template elements before uploading if unintended.")

    report = {
        "doc_errors":        len(errors),
        "doc_warnings":      len(warnings),
        "doc_size":          os.path.getsize(src),
        "pdf_encrypted":     encrypted,
        "doc_errors_list":   errors[:20],
        "doc_warnings_list": warnings[:20],
    }
    return _respond(out, workdir, "application/pdf",
                    {"X-Preflight-Report": json.dumps(report)})


@app.post("/split", dependencies=[Depends(require_api_key)])
def split(file: UploadFile = File(...), page: int = Form(...)):
    """Return one page (1-based) of a multi-page PDF (pdftoolbox --splitpdf)."""
    workdir = tempfile.mkdtemp(prefix="callas_")
    src = _save_upload(file, workdir, "in.pdf")
    out = os.path.join(workdir, "out.pdf")
    with fitz.open(src) as doc:
        if not 1 <= page <= len(doc):
            shutil.rmtree(workdir, True)
            raise HTTPException(400, f"page {page} out of range 1..{len(doc)}")
        single = fitz.open()
        single.insert_pdf(doc, from_page=page - 1, to_page=page - 1)
        single.save(out, garbage=4, deflate=True)
        single.close()
    return _respond(out, workdir, "application/pdf")


@app.post("/spot-to-cmyk", dependencies=[Depends(require_api_key)])
def spot_to_cmyk(file: UploadFile = File(...)):
    """Template spot colours → CMYK (ConvertTemplateSpotColorsToCMYK KFPX)."""
    workdir = tempfile.mkdtemp(prefix="callas_")
    src = _save_upload(file, workdir, "in.pdf")
    out = os.path.join(workdir, "out.pdf")
    ws.convert_template_colors_to_cmyk(src, out)
    return _respond(out, workdir, "application/pdf")


@app.post("/overlay", dependencies=[Depends(require_api_key)])
def overlay(file: UploadFile = File(...), overlay: UploadFile = File(...),
            placement: str = Form("Center")):
    """Stamp an overlay or cutpath PDF on the art (pdftoolbox --overlay)."""
    if placement not in ("Center", "TopCenter"):
        raise HTTPException(400, "placement must be Center or TopCenter")
    workdir = tempfile.mkdtemp(prefix="callas_")
    src = _save_upload(file, workdir, "in.pdf")
    ov  = _save_upload(overlay, workdir, "overlay.pdf")
    out = os.path.join(workdir, "out.pdf")
    ws.stamp_overlay(src, out, ov, opacity=1.0, placement=placement)
    return _respond(out, workdir, "application/pdf")


@app.post("/jpeg", dependencies=[Depends(require_api_key)])
def jpeg(file: UploadFile = File(...), dpi: int = Form(72)):
    """Low-res preview of the first page (pdftoolbox --saveasimg)."""
    if not 1 <= dpi <= 300:
        raise HTTPException(400, "dpi must be 1..300")
    workdir = tempfile.mkdtemp(prefix="callas_")
    src = _save_upload(file, workdir, "in.pdf")
    paths = ws.export_jpeg(src, os.path.join(workdir, "out.jpg"), dpi=dpi)
    return _respond(paths[0], workdir, "image/jpeg")


@app.post("/finish", dependencies=[Depends(require_api_key)])
def finish(file: UploadFile = File(...), product: str = Form(...),
           order_name: str = Form("")):
    """Recipe finishing → production PDF (pdftoolbox finishing KFPX)."""
    recipe = find_recipe(product)
    if recipe is None:
        raise HTTPException(404, f"No callas-app recipe for product '{product}'")
    workdir = tempfile.mkdtemp(prefix="callas_")
    src = _save_upload(file, workdir, "in.pdf")

    # Art is already preflighted, overlaid and cut by earlier calls; run finishing only
    recipe = dict(recipe, preflight="", overlay="", cutpath="", check_size={})
    lbl = recipe.get("labels") or (recipe["finishing"] if isinstance(recipe.get("finishing"), dict)
                                   and recipe["finishing"].get("type") == "flag_label" else None)
    if lbl is not None:
        _fetch_cutpath(lbl.get("cutpath"))
        if order_name:
            # ponytail: var_order_name equivalent — fills the recipe's "ORDER #00000" placeholder
            lbl = dict(lbl, placeholder=lbl.get("placeholder", "ORDER #00000").replace("00000", order_name))
            recipe["labels"] = lbl
    _fetch_cutpath(recipe.get("impose_cutpath"))
    _fetch_cutpath(recipe.get("finishing_cutpath"))

    result = ws.run_recipe(src, recipe, profiles_dir=str(PROFILES_DIR),
                           cutpaths_dir=str(CUTPATHS_DIR),
                           order_name=order_name or None)
    out = os.path.join(workdir, "out.pdf")
    shutil.copy2(result["finished_pdf"], out)
    return _respond(out, workdir, "application/pdf")
