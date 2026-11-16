"""Tests for callas_api.py.  Run:  python -m pytest tests -q"""

import json, os, sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
KEY = "test-key"


def make_pdf(path, w_in=10, h_in=8, pages=1, color=(1, 0, 0)):
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=w_in * 72, height=h_in * 72)
        page.draw_rect(page.rect, color=color, fill=color)
        page.insert_text((20, 40), f"page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def client(tmp_path, monkeypatch):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "banner-10x8.json").write_text(json.dumps({
        "type": "recipe", "name": "banner-10x8", "preflight": "60-50-50-100",
        "check_size": {"width_inch": 10, "height_inch": 8},
    }))
    (profiles / "no-finish.json").write_text(json.dumps({"type": "recipe", "name": "no-finish"}))
    monkeypatch.setenv("CALLAS_API_KEY", KEY)
    monkeypatch.setenv("CALLAS_PROFILES_DIR", str(profiles))
    import importlib, callas_api
    importlib.reload(callas_api)
    from fastapi.testclient import TestClient
    return TestClient(callas_api.app)


def post(client, url, files, data=None, key=KEY):
    opened = {k: (Path(v).name, open(v, "rb"), "application/pdf") for k, v in files.items()}
    try:
        return client.post(url, files=opened, data=data or {}, headers={"X-Api-Key": key})
    finally:
        for _, fh, _ in opened.values():
            fh.close()


def report(resp):
    return json.loads(resp.headers["X-Preflight-Report"])


def test_unicode_logging_survives_cp1252_stdout():
    import subprocess
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    r = subprocess.run([sys.executable, "-c", "import callas_api; print('→')"],
                       cwd=Path(__file__).parent.parent, env=env, capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors="replace")


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_rejects_bad_api_key(client, tmp_path):
    pdf = make_pdf(tmp_path / "a.pdf")
    assert post(client, "/preflight", {"file": pdf}, {"product": "banner-10x8"}, key="wrong").status_code == 401


def test_preflight_passes_correct_size(client, tmp_path):
    resp = post(client, "/preflight", {"file": make_pdf(tmp_path / "a.pdf")}, {"product": "banner-10x8"})
    assert resp.status_code == 200
    r = report(resp)
    assert r["doc_errors"] == 0 and r["pdf_encrypted"] is False and r["doc_size"] > 0
    assert fitz.open(stream=resp.content, filetype="pdf").page_count == 1


def test_preflight_fails_wrong_size(client, tmp_path):
    resp = post(client, "/preflight", {"file": make_pdf(tmp_path / "a.pdf", 12, 8)}, {"product": "banner-10x8"})
    r = report(resp)
    assert r["doc_errors"] == 1 and "width mismatch" in r["doc_errors_list"][0]


def test_preflight_variable_size_overrides_recipe(client, tmp_path):
    resp = post(client, "/preflight", {"file": make_pdf(tmp_path / "a.pdf", 12, 6)},
                {"product": "banner-10x8", "width_in": "12", "height_in": "6"})
    assert report(resp)["doc_errors"] == 0


def test_preflight_unknown_product_is_error(client, tmp_path):
    r = report(post(client, "/preflight", {"file": make_pdf(tmp_path / "a.pdf")}, {"product": "nope"}))
    assert r["doc_errors"] == 1 and "No callas-app recipe" in r["doc_errors_list"][0]


def test_preflight_encrypted(client, tmp_path):
    src = make_pdf(tmp_path / "plain.pdf")
    enc = tmp_path / "enc.pdf"
    doc = fitz.open(str(src))
    doc.save(str(enc), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    doc.close()
    assert report(post(client, "/preflight", {"file": enc}, {"product": "banner-10x8"}))["pdf_encrypted"] is True


def add_spots(path, names):
    """Reference a Separation colour space per name from page 1, as WS templates do."""
    doc = fitz.open(str(path))
    kind, res = doc.xref_get_key(doc[0].xref, "Resources")
    res_xref = int(res.split()[0]) if kind == "xref" else doc[0].xref
    prefix = "" if kind == "xref" else "Resources/"
    for i, name in enumerate(names):
        xref = doc.get_new_xref()
        doc.update_object(xref, f"[/Separation /{name.replace(' ', '#20')} /DeviceCMYK "
                                "<</FunctionType 2 /Domain [0 1] /C0 [0 0 0 0] /C1 [1 0 0 0] /N 1>>]")
        doc.xref_set_key(res_xref, f"{prefix}ColorSpace/CS{i}", f"{xref} 0 R")
    doc.saveIncr()
    doc.close()
    return path


def test_preflight_template_elements_warn(client, tmp_path):
    pdf = add_spots(make_pdf(tmp_path / "t.pdf"), ["Blue Template Layer", "Red Template Layer", "PANTONE 185 C"])
    r = report(post(client, "/preflight", {"file": pdf}, {"product": "no-finish"}))
    assert r["doc_errors"] == 0 and r["doc_warnings"] == 1
    assert "Blue Template Layer, Red Template Layer" in r["doc_warnings_list"][0]
    # KFPX names QuickProof's ProofMessage.GetWarningMessage matches on
    assert r["doc_warning_list"] == [{"name": "Blue Template Color Used"}, {"name": "Red Template Color Used"}]


def test_preflight_clean_file_no_warnings(client, tmp_path):
    pdf = add_spots(make_pdf(tmp_path / "c.pdf"), ["PANTONE 185 C"])
    r = report(post(client, "/preflight", {"file": pdf}, {"product": "no-finish"}))
    assert r["doc_warnings"] == 0 and r["doc_warnings_list"] == [] and r["doc_warning_list"] == []


def test_upload_pdf_renamed_ai_passes_through(client, tmp_path):
    ai = tmp_path / "art.ai"
    make_pdf(tmp_path / "a.pdf").rename(ai)
    resp = post(client, "/preflight", {"file": ai}, {"product": "banner-10x8"})
    assert resp.status_code == 200 and report(resp)["doc_errors"] == 0


def test_upload_unreadable_file_is_422(client, tmp_path):
    txt = tmp_path / "notes.pdf"
    txt.write_text("just some text")
    assert post(client, "/preflight", {"file": txt}, {"product": "banner-10x8"}).status_code == 422


def test_upload_eps_converted(client, tmp_path):
    import ws_pdf_tools
    if not ws_pdf_tools._find_ghostscript():
        pytest.skip("Ghostscript not installed")
    eps = tmp_path / "art.eps"
    eps.write_text("%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 720 576\n"
                   "0 0 1 0 setcmykcolor 0 0 720 576 rectfill showpage\n%%EOF\n")
    resp = post(client, "/preflight", {"file": eps}, {"product": "banner-10x8"})
    assert resp.status_code == 200 and report(resp)["doc_errors"] == 0


def test_split_returns_requested_page(client, tmp_path):
    resp = post(client, "/split", {"file": make_pdf(tmp_path / "m.pdf", pages=3)}, {"page": "2"})
    doc = fitz.open(stream=resp.content, filetype="pdf")
    assert doc.page_count == 1 and "page 2" in doc[0].get_text()


def test_split_out_of_range(client, tmp_path):
    assert post(client, "/split", {"file": make_pdf(tmp_path / "m.pdf", pages=2)}, {"page": "5"}).status_code == 400


@pytest.mark.parametrize("placement", ["Center", "TopCenter"])
def test_overlay(client, tmp_path, placement):
    art = make_pdf(tmp_path / "art.pdf", 10, 8)
    ov = make_pdf(tmp_path / "ov.pdf", 10, 4, color=(0, 0, 1))
    resp = post(client, "/overlay", {"file": art, "overlay": ov}, {"placement": placement})
    assert resp.status_code == 200
    page = fitz.open(stream=resp.content, filetype="pdf")[0]
    pix = page.get_pixmap(dpi=10)
    top, bottom = pix.pixel(pix.width // 2, 2), pix.pixel(pix.width // 2, pix.height - 3)
    blue = lambda px: px[2] > 200 and px[0] < 60
    # Centered 10x4 overlay on 10x8 art leaves red top and bottom bands; TopCenter covers the top
    assert blue(top) == (placement == "TopCenter") and not blue(bottom)


def test_overlay_rejects_bad_placement(client, tmp_path):
    art = make_pdf(tmp_path / "art.pdf")
    assert post(client, "/overlay", {"file": art, "overlay": art}, {"placement": "Left"}).status_code == 400


def test_jpeg(client, tmp_path):
    resp = post(client, "/jpeg", {"file": make_pdf(tmp_path / "a.pdf")}, {"dpi": "32"})
    assert resp.status_code == 200 and resp.content[:2] == b"\xff\xd8"


def test_spot_to_cmyk_returns_pdf(client, tmp_path):
    resp = post(client, "/spot-to-cmyk", {"file": make_pdf(tmp_path / "a.pdf")})
    assert resp.status_code == 200 and resp.content[:4] == b"%PDF"


def test_finish_without_finishing_returns_art(client, tmp_path):
    resp = post(client, "/finish", {"file": make_pdf(tmp_path / "a.pdf")}, {"product": "no-finish", "order_name": "SO1"})
    assert resp.status_code == 200 and fitz.open(stream=resp.content, filetype="pdf").page_count == 1


def test_finish_unknown_product_404(client, tmp_path):
    assert post(client, "/finish", {"file": make_pdf(tmp_path / "a.pdf")}, {"product": "nope"}).status_code == 404
