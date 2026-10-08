from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ReportingPeriod(models.Model):
    """
    Один отчётный период кафедры (напр. «2026-mart» или «31.12.2026 holatiga»).
    Это и есть та точка, к которой привязаны все факт-таблицы показателей —
    вместо того чтобы каждый раз пересоздавать 20 листов вручную, данные
    накапливаются по преподавателям/студентам и группируются запросом по
    reporting_period при формировании отчёта.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик (преподаватели вводят данные)")
        SUBMITTED = "submitted", _("Отправлено на согласование")
        APPROVED = "approved", _("Утверждено")

    department = models.ForeignKey(
        "core.Department", on_delete=models.PROTECT, related_name="reporting_periods",
        verbose_name=_("Кафедра"),
    )
    period_label = models.CharField(
        _("Метка периода"), max_length=50, help_text=_("Например: 2026-mart"),
    )
    period_date = models.DateField(_("Дата, на которую формируется отчёт (holatiga)"))
    status = models.CharField(
        _("Статус"), max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    # Показатели уровня кафедры — в форме они не «на человека», а одно число
    # на всю кафедру (последняя колонка листов 3,2 / 3,3 / 4,1 / 4,2 и шапка 5).
    staff_units = models.DecimalField(
        _("Выделенные штатные единицы (лист 5)"), max_digits=6, decimal_places=2,
        null=True, blank=True,
    )
    total_students_count = models.PositiveIntegerField(
        _("Общее число студентов бакалавриата и магистратуры (листы 3,2 и 3,3)"),
        null=True, blank=True,
    )
    total_graduates_count = models.PositiveIntegerField(
        _("Общее число выпускников (листы 4,1 и 4,2)"), null=True, blank=True,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="submitted_periods", verbose_name=_("Отправил на согласование"),
    )
    submitted_at = models.DateTimeField(_("Отправлено"), null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_periods", verbose_name=_("Утвердил"),
    )
    approved_at = models.DateTimeField(_("Утверждено"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Отчётный период")
        verbose_name_plural = _("Отчётные периоды")
        unique_together = [("department", "period_label")]
        ordering = ["-period_date"]

    def __str__(self):
        return f"{self.department} — {self.period_label}"

    @property
    def is_open(self):
        """Преподаватели могут добавлять и править записи только пока период
        в статусе «черновик» — после отправки данные заморожены."""
        return self.status == self.Status.DRAFT
