from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import ReportingPeriod


@admin.register(ReportingPeriod)
class ReportingPeriodAdmin(admin.ModelAdmin):
    list_display = ("department", "period_label", "period_date", "status", "approved_at")
    list_filter = ("status", "department")
    search_fields = ("period_label",)
    autocomplete_fields = ("department",)
    readonly_fields = ("submitted_by", "submitted_at", "approved_by", "approved_at")
    fieldsets = (
        (None, {"fields": ("department", "period_label", "period_date", "status")}),
        (_("Показатели уровня кафедры"), {
            "fields": ("staff_units", "total_students_count", "total_graduates_count"),
            "description": _("Одно число на всю кафедру: шапка листа 5 и последние колонки "
                             "листов 3,2 / 3,3 / 4,1 / 4,2."),
        }),
        (_("Согласование"), {"fields": ("submitted_by", "submitted_at", "approved_by", "approved_at")}),
    )
    actions = ["mark_submitted", "mark_approved", "mark_draft"]

    @admin.action(description=_("Отметить как «отправлено на согласование» (ввод закрывается)"))
    def mark_submitted(self, request, queryset):
        queryset.update(
            status=ReportingPeriod.Status.SUBMITTED,
            submitted_by=request.user,
            submitted_at=timezone.now(),
        )

    @admin.action(description=_("Утвердить период"))
    def mark_approved(self, request, queryset):
        queryset.update(
            status=ReportingPeriod.Status.APPROVED,
            approved_by=request.user,
            approved_at=timezone.now(),
        )

    @admin.action(description=_("Вернуть в черновик (снова открыть ввод для преподавателей)"))
    def mark_draft(self, request, queryset):
        queryset.update(status=ReportingPeriod.Status.DRAFT)
