"""Enregistrement des exécutions import_* dans ImportLog."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from .models import ImportLog

User = get_user_model()


def record_import_run(
    *,
    command_name: str,
    file_name: str = "",
    success_count: int = 0,
    error_lines: list[str] | None = None,
    admin_user_id: int | None = None,
) -> ImportLog:
    err = "\n".join(error_lines or [])[:500_000]
    user = None
    if admin_user_id:
        user = User.objects.filter(pk=admin_user_id).first()
    return ImportLog.objects.create(
        command_name=command_name[:128],
        file_name=(file_name or "")[:512],
        success_count=max(0, int(success_count)),
        error_log=err,
        admin_user=user,
    )
