from collections import defaultdict
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.exporter.archive import collect_documents, export_archive
from apps.exporter.engine import build_workbook, export_report
from apps.portal.registry import REGISTRY
from apps.staff.models import TeacherPeriodSnapshot
from apps.workflow.models import ReportingPeriod


def staff_only(view):
    """Отчёты кафедры (и архив с дипломами всех сотрудников) видит только
    персонал кафедры; преподавателя отправляем в его кабинет."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            if getattr(request.user, "teacher_profile", None):
                return redirect("portal:index")
            raise Http404
        return view(request, *args, **kwargs)

    return wrapped


def _periods():
    return ReportingPeriod.objects.select_related("department").order_by("-period_date")


@staff_only
def index(request):
    return render(request, "dashboard/index.html", {"periods": _periods()[:100]})


@staff_only
def progress(request, period_id):
    period = get_object_or_404(_periods(), pk=period_id)
    snaps = (TeacherPeriodSnapshot.objects.filter(reporting_period=period)
             .select_related("teacher", "teacher__user", "employment_type")
             .order_by("employment_type__sort_order", "teacher__full_name"))

    counts = defaultdict(lambda: defaultdict(int))
    for slug, cfg in REGISTRY.items():
        model = cfg["model"].objects.filter(reporting_period=period)
        if cfg.get("authors"):
            for obj in model.prefetch_related("authors"):
                for a in obj.authors.all():
                    counts[a.id][slug] += 1
        else:
            for teacher_id in model.values_list(f'{cfg["teacher_field"]}_id', flat=True):
                counts[teacher_id][slug] += 1

    missing = defaultdict(list)
    for doc in collect_documents(period):
        if not doc.present:
            for tid in doc.teacher_ids:
                missing[tid].append(f"{doc.section}: {doc.title}")

    rows = [{
        "snap": s,
        "cells": [counts[s.teacher_id].get(slug, 0) for slug in REGISTRY],
        "missing": missing.get(s.teacher_id, []),
    } for s in snaps]

    _, _, warnings = build_workbook(period)
    return render(request, "dashboard/progress.html", {
        "period": period, "rows": rows,
        "sections": [(cfg["sheet"], cfg["title"]) for cfg in REGISTRY.values()],
        "warnings": warnings,
    })


@staff_only
def download_report(request, period_id):
    period = get_object_or_404(_periods(), pk=period_id)
    try:
        path, _, _ = export_report(period.department, period)
    except FileNotFoundError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)


@staff_only
def download_files(request, period_id):
    period = get_object_or_404(_periods(), pk=period_id)
    path, _ = export_archive(period)
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)


@login_required
def home(request):
    if request.user.is_staff:
        return redirect("dashboard:index")
    return redirect("portal:index")
