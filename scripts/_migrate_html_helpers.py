"""One-off helpers to convert static HTML fragments to Django templates."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (pattern, replacement) — order matters (specific before generic)
# Use non-raw replacement strings so {% url 'app:name' %} is valid Django template syntax.
LINK_REPLACEMENTS = [
    (r'href="index\.html#([^"]+)"', 'href="{% url \'website:index\' %}#\\1"'),
    (r'href="index\.html"', 'href="{% url \'website:index\' %}"'),
    (r'href="cartes\.html"', 'href="{% url \'website:cartes\' %}"'),
    (r'href="atlas\.html"', 'href="{% url \'website:atlas\' %}"'),
    (r'href="a-propos\.html"', 'href="{% url \'website:a_propos\' %}"'),
    (r'href="contact\.html"', 'href="{% url \'website:contact\' %}"'),
    (r'href="faq\.html"', 'href="{% url \'website:faq\' %}"'),
    (r'href="partenaire\.html"', 'href="{% url \'website:partenaire\' %}"'),
    (r'href="connexion\.html"', 'href="{% url \'accounts:login\' %}"'),
    (r'href="inscription\.html"', 'href="{% url \'accounts:register\' %}"'),
    (r'href="\.\./connexion\.html"', 'href="{% url \'accounts:login\' %}"'),
    (r'href="\.\./inscription\.html"', 'href="{% url \'accounts:register\' %}"'),
    (r'href="\.\./atlas\.html"', 'href="{% url \'website:atlas\' %}"'),
    (r'href="\.\./index\.html"', 'href="{% url \'website:index\' %}"'),
]


def staticify_assets(html: str) -> str:
    """Replace assets/... in src, href (css), and url() in style attributes."""

    def _repl(m):
        attr, path = m.group(1), m.group(2)
        tag = "{{% static 'assets/{}' %}}".format(path)
        return '{}="{}"'.format(attr, tag)

    html = re.sub(
        r'(src|href)="assets/([^"]+)"',
        _repl,
        html,
    )
    return html


DASHBOARD_LINKS = [
    (r'href="client-home\.html"', 'href="{% url \'accounts:dashboard_client\' %}"'),
    (r'href="client-library\.html"', 'href="{% url \'accounts:dashboard_library\' %}"'),
    (r'href="client-billing\.html"', 'href="{% url \'accounts:dashboard_billing\' %}"'),
    (r'href="client-settings\.html"', 'href="{% url \'accounts:dashboard_settings\' %}"'),
    (r'href="client-store\.html"', 'href="{% url \'accounts:dashboard_store\' %}"'),
]


def apply_page_links(html: str) -> str:
    for pat, repl in LINK_REPLACEMENTS:
        html = re.sub(pat, repl, html)
    return html


def apply_dashboard_links(html: str) -> str:
    for pat, repl in DASHBOARD_LINKS:
        html = re.sub(pat, repl, html)
    return html


def convert_fragment(html: str) -> str:
    html = staticify_assets(html)
    html = apply_page_links(html)
    return html


def staticify_dashboard(html: str) -> str:
    """Paths relative to dashboard/*.html: assets/ -> static/dashboard_assets/."""

    def _repl(m):
        attr, path = m.group(1), m.group(2)
        tag = "{{% static 'dashboard_assets/{}' %}}".format(path)
        return '{}="{}"'.format(attr, tag)

    html = re.sub(r'(src|href)="assets/([^"]+)"', _repl, html)

    def _repl_up(m):
        path = m.group(1)
        tag = "{{% static 'assets/{}' %}}".format(path)
        return 'src="{}"'.format(tag)

    html = re.sub(r'src="\.\./assets/([^"]+)"', _repl_up, html)
    html = apply_dashboard_links(html)
    html = apply_page_links(html)
    return html
