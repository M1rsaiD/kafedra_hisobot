from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from apps.workflow.models import ReportingPeriod
from apps.exporter.engine import export_report


@login_required
def index(request):
    periods = (
        ReportingPeriod.objects.select_related("department")
        .order_by("-period_date")[:100]
    )
    return render(request, "dashboard/index.html", {"periods": periods})


@login_required
def download_report(request, period_id):
    period = get_object_or_404(ReportingPeriod.objects.select_related("department"), pk=period_id)
    try:
        path, filled, skipped = export_report(period.department, period)
    except FileNotFoundError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)
