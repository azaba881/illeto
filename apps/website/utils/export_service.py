"""
Headless Atlas map capture via Playwright (PNG/PDF), with Pillow watermark and cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

_export_semaphore = threading.BoundedSemaphore(
    max(1, int(getattr(settings, "ILLETO_EXPORT_MAX_CONCURRENT", 2)))
)


def _cache_ttl_seconds() -> int:
    return int(getattr(settings, "ILLETO_ATLAS_EXPORT_CACHE_TTL", 86400))


def _cache_dir() -> Path:
    p = Path(getattr(settings, "ILLETO_ATLAS_EXPORT_CACHE_DIR", ""))
    if not p.is_absolute():
        p = Path(settings.BASE_DIR) / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def normalize_export_payload_for_key(data: dict[str, Any]) -> dict[str, Any]:
    """Stable subset for cache key (no map_state / large blobs duplicated unnecessarily)."""
    c = data.get("center") or {}
    clip = data.get("clip") or {}
    vp = data.get("viewport") or {}
    out: dict[str, Any] = {
        "lat": round(float(c.get("lat", 0)), 6),
        "lng": round(float(c.get("lng", 0)), 6),
        "zoom": round(float(data.get("zoom", 0)), 4),
        "basemap": str(data.get("basemap", "")),
        "pitch": round(float(data.get("pitch", 0)), 2),
        "bearing": round(float(data.get("bearing", 0)), 2),
        "vue3d": bool(data.get("vue3d")),
        "format": str(data.get("format", "png")).lower(),
        "clip_x": int(round(float(clip.get("x", 0)))),
        "clip_y": int(round(float(clip.get("y", 0)))),
        "clip_w": int(round(float(clip.get("width", 0)))),
        "clip_h": int(round(float(clip.get("height", 0)))),
        "vp_w": int(round(float(vp.get("width", 0)))),
        "vp_h": int(round(float(vp.get("height", 0)))),
        "selected_feature_id": data.get("selected_feature_id"),
        "hide_selection": bool(data.get("hideSelectionStyle")),
        "nom_dept": str(data.get("nom_departement") or ""),
        "export_user": str(data.get("export_user_label") or ""),
    }
    fg = data.get("fit_geometry")
    if fg is not None:
        out["fit_geometry"] = json.dumps(fg, sort_keys=True, separators=(",", ":"))
    out["fit_max_zoom"] = round(float(data.get("fit_max_zoom", 12)), 2)
    return out


def export_cache_key(data: dict[str, Any]) -> str:
    normalized = normalize_export_payload_for_key(data)
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cache_paths(key: str, fmt: str) -> tuple[Path, Path]:
    d = _cache_dir()
    ext = "pdf" if fmt == "pdf" else "png"
    return d / f"{key}.{ext}", d / f"{key}.meta.json"


def _cache_is_fresh(path: Path) -> bool:
    if not path.is_file():
        return False
    age = time.time() - path.stat().st_mtime
    return age < _cache_ttl_seconds()


def apply_png_watermark(png_bytes: bytes, text: str = "IlèTô Atlas") -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(BytesIO(png_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(im)
    w, h = im.size
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except OSError:
            font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 16
    x, y = w - tw - pad, h - th - pad
    draw.text((x + 1, y + 1), text, fill=(0, 0, 0, 200), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, 245), font=font)
    out = BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def _register_pdf_unicode_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    cache = getattr(_register_pdf_unicode_fonts, "_cache", None)
    if cache:
        return cache  # type: ignore[return-value]
    reg = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bd = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    try:
        if reg.is_file():
            pdfmetrics.registerFont(TTFont("IlletoDejaVu", str(reg)))
            if bd.is_file():
                pdfmetrics.registerFont(TTFont("IlletoDejaVuBd", str(bd)))
                _register_pdf_unicode_fonts._cache = ("IlletoDejaVu", "IlletoDejaVuBd")  # type: ignore[attr-defined]
            else:
                _register_pdf_unicode_fonts._cache = ("IlletoDejaVu", "IlletoDejaVu")  # type: ignore[attr-defined]
            return _register_pdf_unicode_fonts._cache  # type: ignore[attr-defined]
    except Exception:
        pass
    _register_pdf_unicode_fonts._cache = ("Helvetica", "Helvetica-Bold")  # type: ignore[attr-defined]
    return _register_pdf_unicode_fonts._cache  # type: ignore[attr-defined]


def png_bytes_to_pdf_atlas(
    map_png_bytes: bytes,
    *,
    request,
    payload: dict[str, Any],
) -> bytes:
    """A4 : cartouche sombre (badge + ILÊTÔ), titre officiel, métadonnées, carte bordée, pied de page."""
    from datetime import datetime

    from PIL import Image
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    W, H = A4
    margin = 40
    header_h = 118
    footer_h = 36
    sep_pt = 1

    font, font_bold = _register_pdf_unicode_fonts()

    ctr = payload.get("center") or {}
    try:
        lat = float(ctr.get("lat", 0))
        lng = float(ctr.get("lng", 0))
    except (TypeError, ValueError):
        lat, lng = 0.0, 0.0
    nom_dept = (payload.get("nom_departement") or "").strip()
    user_label = (payload.get("export_user_label") or "").strip()
    if not user_label and getattr(request, "user", None) is not None:
        u = request.user
        if u.is_authenticated:
            try:
                fn = (u.get_full_name() or "").strip()
            except Exception:
                fn = ""
            user_label = fn or (getattr(u, "email", None) or "") or str(u.pk)
    if not user_label:
        user_label = "Visiteur"

    badge_path_str = getattr(settings, "ILLETO_ATLAS_PDF_BADGE_PATH", "") or ""
    badge_path = Path(badge_path_str) if badge_path_str else None
    if badge_path and not badge_path.is_file():
        badge_path = None

    pdf_buf = BytesIO()
    cnv = canvas.Canvas(pdf_buf, pagesize=A4)

    header_bottom = H - header_h
    cnv.setFillColor(colors.HexColor("#03050c"))
    cnv.rect(0, header_bottom, W, header_h, fill=1, stroke=0)

    badge_size = 50
    badge_x = margin
    badge_y = H - margin - badge_size
    if badge_path and badge_path.is_file():
        try:
            cnv.drawImage(
                str(badge_path),
                badge_x,
                badge_y,
                width=badge_size,
                height=badge_size,
                mask="auto",
            )
        except Exception:
            logger.debug("Badge PDF absent ou illisible", exc_info=True)

    cnv.setFillColor(colors.HexColor("#e2e8f0"))
    cnv.setFont(font, 8)
    tag = "ILÊTÔ : INTELLIGENCE TERRITORIALE"
    cnv.drawString(badge_x + badge_size + 10, H - margin - 18, tag)

    title = "RAPPORT CARTOGRAPHIQUE OFFICIEL"
    cnv.setFont(font_bold, 13)
    tw = cnv.stringWidth(title, font_bold, 13)
    cnv.drawString((W - tw) / 2, H - margin - 22, title)

    cnv.setFont(font, 9)
    if nom_dept:
        dept_line = f"Département : {nom_dept}"
        dw = cnv.stringWidth(dept_line, font, 9)
        cnv.drawString((W - dw) / 2, H - margin - 38, dept_line)
    coord_line = f"Centre de vue : {lat:.6f}°, {lng:.6f}°"
    cw = cnv.stringWidth(coord_line, font, 9)
    cnv.drawString((W - cw) / 2, H - margin - 52, coord_line)

    now = datetime.now()
    date_str = now.strftime("%d/%m/%Y %H:%M")
    right_x = W - margin
    cnv.setFont(font, 8)
    cnv.drawRightString(right_x, H - margin - 18, date_str)
    cnv.drawRightString(right_x, H - margin - 30, f"Utilisateur : {user_label}")
    cnv.drawRightString(right_x, H - margin - 42, f"Lat. {lat:.5f}° / Long. {lng:.5f}°")

    cnv.setStrokeColor(colors.HexColor("#00875a"))
    cnv.setLineWidth(sep_pt)
    line_y = header_bottom
    cnv.line(margin, line_y, W - margin, line_y)

    pil_im = Image.open(BytesIO(map_png_bytes))
    iw, ih = pil_im.size
    max_map_w = W - 2 * margin
    max_map_h = H - header_h - footer_h - 50
    scale = min(max_map_w / iw, max_map_h / ih)
    draw_w = iw * scale
    draw_h = ih * scale
    ix = (W - draw_w) / 2
    iy = footer_h + (max_map_h - draw_h) / 2

    cnv.drawImage(
        ImageReader(BytesIO(map_png_bytes)), ix, iy, width=draw_w, height=draw_h
    )

    cnv.setStrokeColor(colors.black)
    cnv.setLineWidth(2)
    cnv.rect(ix, iy, draw_w, draw_h, fill=0, stroke=1)

    cnv.setFont(font, 8)
    cnv.setFillColor(colors.HexColor("#475569"))
    foot = f"Copyright {now.year} - IlèTô Atlas - Bénin"
    fw = cnv.stringWidth(foot, font, 8)
    cnv.drawString((W - fw) / 2, 22, foot)

    cnv.showPage()
    cnv.save()
    return pdf_buf.getvalue()


def _cookies_for_playwright(request, base_url: str) -> list[dict[str, str]]:
    """Playwright : un cookie doit être {name, value, url} OU {name, value, domain, path} — pas url+path."""
    from urllib.parse import urlparse

    p = urlparse(base_url)
    if not p.scheme or not p.netloc:
        return []
    origin = f"{p.scheme}://{p.netloc}"
    page_url = origin + "/"
    out: list[dict[str, str]] = []
    for k, v in request.COOKIES.items():
        if not k:
            continue
        val = v if isinstance(v, str) else str(v)
        out.append({"name": str(k), "value": val, "url": page_url})
    return out


def capture_atlas_export(
    request,
    payload: dict[str, Any],
    *,
    atlas_path: str = "/atlas/",
) -> tuple[bytes, str, str]:
    """
    Run Playwright headless capture. Returns (body_bytes, mime_type, suggested_filename).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright n'est pas installé. Ajoutez playwright au projet et exécutez "
            "`playwright install chromium`."
        ) from e

    fmt = str(payload.get("format", "png")).lower()
    if fmt not in ("png", "pdf"):
        fmt = "png"

    cache_key = export_cache_key(payload)
    cache_file, meta_file = _cache_paths(cache_key, fmt)
    if _cache_is_fresh(cache_file):
        data = cache_file.read_bytes()
        fname = f"Illeto_atlas_{cache_key[:12]}.{fmt}"
        mime = "application/pdf" if fmt == "pdf" else "image/png"
        return data, mime, fname

    base = request.build_absolute_uri("/").rstrip("/")
    atlas_url = base + (atlas_path if atlas_path.startswith("/") else "/" + atlas_path)
    cookies = _cookies_for_playwright(request, base + "/")

    clip = payload.get("clip") or {}
    clip_w = int(round(float(clip.get("width", 0))))
    clip_h = int(round(float(clip.get("height", 0))))
    clip_x = int(round(float(clip.get("x", 0))))
    clip_y = int(round(float(clip.get("y", 0))))
    max_dim = int(getattr(settings, "ILLETO_ATLAS_EXPORT_MAX_CLIP", 2400))
    if clip_w < 16 or clip_h < 16 or clip_w > max_dim or clip_h > max_dim:
        raise ValueError("Dimensions de capture invalides.")

    eval_payload = {
        "center": payload.get("center"),
        "zoom": payload.get("zoom"),
        "basemap": payload.get("basemap", "dark"),
        "pitch": payload.get("pitch", 0),
        "bearing": payload.get("bearing", 0),
        "vue3d": payload.get("vue3d", False),
        "fit_geometry": payload.get("fit_geometry"),
        "fit_max_zoom": payload.get("fit_max_zoom", 12),
        "hideSelectionStyle": bool(payload.get("hideSelectionStyle")),
    }

    dpr = float(getattr(settings, "ILLETO_ATLAS_EXPORT_DEVICE_SCALE", 2))
    png_out: bytes | None = None

    _export_semaphore.acquire()
    try:
        if _cache_is_fresh(cache_file):
            data = cache_file.read_bytes()
            fname = f"Illeto_atlas_{cache_key[:12]}.{fmt}"
            mime = "application/pdf" if fmt == "pdf" else "image/png"
            return data, mime, fname

        vp = payload.get("viewport") or {}
        try:
            vw = int(round(float(vp.get("width") or 1280)))
            vh = int(round(float(vp.get("height") or 720)))
        except (TypeError, ValueError):
            vw, vh = 1280, 720
        vw = max(400, min(vw, 3840))
        vh = max(400, min(vh, 2160))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": vw, "height": vh},
                    device_scale_factor=dpr,
                    ignore_https_errors=True,
                )
                context.add_init_script(
                    "window.__ILLETO_ATLAS_HEADLESS_EXPORT__ = true;"
                )
                if cookies:
                    context.add_cookies(cookies)
                page = context.new_page()
                page.set_default_timeout(
                    int(getattr(settings, "ILLETO_ATLAS_EXPORT_TIMEOUT_MS", 120000))
                )
                page.goto(atlas_url, wait_until="networkidle", timeout=120000)
                page.wait_for_selector("#map", state="visible", timeout=60000)
                page.wait_for_function(
                    "window.IlletoAtlasMap && typeof window.IlletoAtlasMap.runPlaywrightExport === 'function'",
                    timeout=60000,
                )
                page.evaluate(
                    "(cfg) => window.IlletoAtlasMap.runPlaywrightExport(cfg)",
                    eval_payload,
                )
                try:
                    page.wait_for_load_state("networkidle", timeout=45000)
                except Exception:
                    logger.debug("networkidle après export ignoré", exc_info=True)
                page.wait_for_timeout(
                    int(getattr(settings, "ILLETO_ATLAS_EXPORT_POST_IDLE_MS", 800))
                )
                clip_x = max(0, min(clip_x, vw - 1))
                clip_y = max(0, min(clip_y, vh - 1))
                clip_w = max(16, min(clip_w, vw - clip_x))
                clip_h = max(16, min(clip_h, vh - clip_y))
                png_out = page.screenshot(
                    type="png",
                    clip={
                        "x": clip_x,
                        "y": clip_y,
                        "width": clip_w,
                        "height": clip_h,
                    },
                )
            finally:
                browser.close()
    finally:
        _export_semaphore.release()

    if not png_out:
        raise RuntimeError("Capture vide.")

    png_out = apply_png_watermark(png_out)
    if fmt == "pdf":
        body = png_bytes_to_pdf_atlas(png_out, request=request, payload=payload)
        mime = "application/pdf"
    else:
        body = png_out
        mime = "image/png"

    try:
        cache_file.write_bytes(body)
        meta_file.write_text(
            json.dumps({"key": cache_key, "ts": time.time()}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        logger.warning("Impossible d'écrire le cache export", exc_info=True)

    fname = f"Illeto_atlas_{cache_key[:12]}.{fmt}"
    return body, mime, fname
