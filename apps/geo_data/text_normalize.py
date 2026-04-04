"""Normalisation des libellés géographiques (mojibake, accents) à l'import.

Utiliser `normalize_boundary_label` sur les noms issus des importeurs (GeoJSON,
OSM, etc.) pour limiter les « ? » et caractères corrompus ; secours Unidecode
lorsque la correction Latin-1/UTF-8 ne suffit pas.
"""

from __future__ import annotations


def normalize_boundary_label(text: str | None) -> str:
    """
    Corrige des chaînes type « Tangbo-Dj?vi? » souvent dues à une mauvaise chaîne
    intermédiaire (UTF-8 relue comme Latin-1). Sinon tente unidécode en secours.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""
    if "?" in s:
        try:
            alt = s.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
            if alt and alt != s and alt.count("?") < s.count("?"):
                return alt.strip()
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        try:
            from unidecode import unidecode

            return unidecode(s).strip() or s
        except ImportError:
            pass
    return s
