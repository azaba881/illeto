"""Tableau de maintenance géo (staff) : imports + complétude par département."""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .models import Commune, Departement, ImportLog


@staff_member_required
def geo_maintenance_dashboard(request):
    logs = ImportLog.objects.select_related("admin_user").order_by("-created_at")[:200]

    completeness = []
    for dept in Departement.objects.order_by("name"):
        communes = Commune.objects.filter(departement=dept, is_placeholder=False)
        total = communes.count()
        with_quartiers = (
            communes.annotate(qc=Count("quartiers"))
            .filter(qc__gt=0)
            .count()
        )
        if total == 0:
            pct = 100
        else:
            pct = int(round(100.0 * with_quartiers / total))
        completeness.append(
            {
                "department": dept,
                "commune_count": total,
                "with_quartiers": with_quartiers,
                "percent_quartiers": pct,
            }
        )

    return render(
        request,
        "admin/geo_maintenance.html",
        {
            "title": "Maintenance géographique",
            "import_logs": logs,
            "completeness": completeness,
        },
    )
