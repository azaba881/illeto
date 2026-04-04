"""Chemins et URLs par défaut depuis les settings (alimentés par .env)."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings


def _path_or_none(key: str) -> Path | None:
    raw = getattr(settings, key, None)
    if not raw or not str(raw).strip():
        return None
    p = Path(str(raw).strip())
    if not p.is_absolute():
        p = Path(settings.BASE_DIR) / p
    return p.resolve()


def hdx_adm1_path() -> Path | None:
    return _path_or_none("ILLETO_HDX_ADM1_PATH")


def hdx_adm2_path() -> Path | None:
    return _path_or_none("ILLETO_HDX_ADM2_PATH")


def hdx_adm3_path() -> Path | None:
    return _path_or_none("ILLETO_HDX_ADM3_PATH")


def overpass_api_url() -> str:
    return getattr(
        settings,
        "ILLETO_OVERPASS_API_URL",
        "https://overpass-api.de/api/interpreter",
    )


def osm_districts_path() -> Path | None:
    return _path_or_none("ILLETO_OSM_DISTRICTS_PATH")


def poi_geojson_path() -> Path | None:
    return _path_or_none("ILLETO_POI_GEOJSON_PATH")


def hydro_geojson_path() -> Path | None:
    return _path_or_none("ILLETO_HYDRO_GEOJSON_PATH")


def resolve_path(cli_value: str | None, env_resolver) -> Path | None:
    """Si ``cli_value`` est non vide, le résoudre ; sinon essayer l’env."""
    if cli_value and str(cli_value).strip():
        p = Path(str(cli_value).strip())
        if not p.is_absolute():
            p = Path(settings.BASE_DIR) / p
        return p.resolve()
    return env_resolver()
