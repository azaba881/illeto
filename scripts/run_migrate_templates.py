#!/usr/bin/env python3
"""Generate Django templates from static HTML (run from project root)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _migrate_html_helpers import convert_fragment  # noqa: E402

# (source_file, start, end, dest, title, template_mode)
# template_mode: "content" = {% block content %}, "shell" = {% block site_shell %} (fullscreen atlas)
WEBSITE_PAGES = [
    ("index.html", 106, 814, "templates/website/index.html", "Illeto | Visualiser le territoire", "content"),
    ("cartes.html", 105, 311, "templates/website/cartes.html", "Illeto | Trouver une carte", "content"),
    ("a-propos.html", None, None, "templates/website/a_propos.html", "Illeto | À propos", "content"),
    ("contact.html", None, None, "templates/website/contact.html", "Illeto | Contact", "content"),
    ("faq.html", None, None, "templates/website/faq.html", "Illeto | FAQ", "content"),
    ("partenaire.html", None, None, "templates/website/partenaire.html", "Illeto | Devenir partenaire", "content"),
    ("atlas.html", 59, 339, "templates/website/atlas.html", "Illeto | Atlas", "shell"),
]

MAIN_PAT = re.compile(r"<main[^>]*>", re.I)


def extract_main(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = MAIN_PAT.search(text)
    if not m:
        raise ValueError(f"No <main> in {path}")
    start = m.start()
    end = text.rfind("</main>")
    if end == -1:
        raise ValueError(f"No </main> in {path}")
    return text[start : end + len("</main>")]


def slice_lines(path: Path, start: int, end: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[start - 1 : end])


def build_page(src_name, start, end, dest, title, mode):
    src = ROOT / src_name
    if start is None:
        inner = extract_main(src)
    else:
        inner = slice_lines(src, start, end)
    inner = convert_fragment(inner)

    if mode == "shell":
        tpl = f'''{{% extends "layouts/base.html" %}}
{{% load static %}}
{{% block title %}}{title}{{% endblock %}}
{{% block body_attr %}} class="bg-background text-foreground font-sans antialiased"{{% endblock %}}
{{% block site_shell %}}
{inner.rstrip()}
{{% endblock %}}
'''
    else:
        tpl = f'''{{% extends "layouts/base.html" %}}
{{% load static %}}
{{% block title %}}{title}{{% endblock %}}
{{% block content %}}
{inner.rstrip()}
{{% endblock %}}
'''
    dest_path = ROOT / dest
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(tpl, encoding="utf-8")
    print("Wrote", dest_path.relative_to(ROOT))


def main():
    for row in WEBSITE_PAGES:
        build_page(*row)


if __name__ == "__main__":
    main()
