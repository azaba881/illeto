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


def png_bytes_to_pdf(png_bytes: bytes) -> bytes:
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = BytesIO(png_bytes)
    im = Image.open(buf)
    w, h = im.size
    pdf_buf = BytesIO()
    buf.seek(0)
    c = canvas.Canvas(pdf_buf, pagesize=(w, h))
    c.drawImage(ImageReader(buf), 0, 0, width=w, height=h)
    c.save()
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
        body = png_bytes_to_pdf(png_out)
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
