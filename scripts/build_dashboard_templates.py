#!/usr/bin/env python3
"""Build dashboard templates from dashboard/*.html."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _migrate_html_helpers import staticify_dashboard  # noqa: E402

# (source, main_start, main_end, dest_name, block_title)
PAGES = [
    ("dashboard/client-home.html", 74, 230, "dashboard_home.html", "Tableau de bord Client - Illeto"),
    ("dashboard/client-library.html", 61, 245, "dashboard_library.html", "Ma Cartothèque - Illeto"),
    ("dashboard/client-billing.html", 61, 210, "dashboard_billing.html", "Facturation - Illeto"),
    ("dashboard/client-settings.html", 62, 154, "dashboard_settings.html", "Paramètres - Illeto"),
    ("dashboard/client-store.html", 61, 312, "dashboard_store.html", "Boutique - Illeto"),
]


def main():
    shell_src = ROOT / "dashboard/client-home.html"
    lines = shell_src.read_text(encoding="utf-8").splitlines(keepends=True)
    # After opening <body>: overlay, topbar, sidebar (lines 14–71, 1-based; skip duplicate <body>)
    shell = "".join(lines[13:71])
    shell = staticify_dashboard(shell)
    base = """{% load static %}
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{% block dashboard_title %}Tableau de bord - Illeto{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'dashboard_assets/css/main.css' %}" />
  <link rel="stylesheet" href="{% static 'dashboard_assets/css/illeto-dashboard-client.css' %}" />
  <script type="module" src="{% static 'dashboard_assets/js/main.js' %}"></script>
</head>
<body>
""" + shell + """
  <main id="content" class="content py-10">
    {% block dashboard_content %}{% endblock %}
  </main>
  <script src="{% static 'dashboard_assets/js/illeto-dashboard-client.js' %}" defer></script>
  {% block dashboard_extra_js %}{% endblock %}
</body>
</html>
"""
    (ROOT / "templates/layouts/dashboard_base.html").write_text(base, encoding="utf-8")
    print("Wrote templates/layouts/dashboard_base.html")

    for src_name, m_start, m_end, dest, title in PAGES:
        src = ROOT / src_name
        lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
        inner = "".join(lines[m_start - 1 : m_end])
        inner = staticify_dashboard(inner)
        # onclick window.location
        inner = inner.replace("window.location='client-store.html'", "window.location='{% url 'accounts:dashboard_store' %}'")
        tpl = f"""{{% extends "layouts/dashboard_base.html" %}}
{{% load static %}}
{{% block dashboard_title %}}{title}{{% endblock %}}
{{% block dashboard_content %}}
{inner.rstrip()}
{{% endblock %}}
"""
        out = ROOT / "templates/accounts" / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(tpl, encoding="utf-8")
        print("Wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
