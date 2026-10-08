from datetime import date

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import Department
from apps.core.validators import DOCUMENT_VALIDATORS
from apps.dictionaries.models import (
    EmploymentType, Position, AcademicDegree, AcademicTitle, Country, ForeignInstitutionRank,
)
from apps.workflow.models import ReportingPeriod


class Teacher(models.Model):
    """
    Мастер-запись преподавателя. Всё, что меняется от периода к периоду
    (должность, ставка, степень на момент отчёта — как в 5-jadval), хранится
    в TeacherPeriodSnapshot, а не здесь, чтобы не терять историю.

    Поля дипломов/приказа/гражданства преподаватель заполняет сам в личном
    кабинете (листы 1,1 / 1,2 / 1,3 / 1,4), файлы уходят в архив отчёта.
    """

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="teachers",
        verbose_name=_("Кафедра"),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="teacher_profile",
        verbose_name=_("Логин в системе"),
        help_text=_("Заводится кафедрой через действие «Создать логин» в списке преподавателей — "
                    "даёт доступ в личный кабинет, где преподаватель сам вносит свои показатели."),
    )
    full_name = models.CharField(_("Ф.И.Ш. (полностью)"), max_length=255)
    birth_date = models.DateField(
        _("Дата рождения"), null=True, blank=True,
        help_text=_("Должна совпадать с паспортом (лист 1,2)."),
    )

    # --- Лист 1,1: диплом об учёной степени + приказ о приёме -------------
    specialty_name = models.CharField(
        _("Специальность по диплому об учёной степени"), max_length=255, blank=True,
    )
    diploma_series = models.CharField(_("Серия диплома"), max_length=10, blank=True)
    diploma_number = models.CharField(_("Номер диплома"), max_length=20, blank=True)
    diploma_file = models.FileField(
        _("Скан диплома об учёной степени / звании (PDF)"), upload_to="teachers/diplomas/",
        null=True, blank=True, validators=DOCUMENT_VALIDATORS,
    )
    foreign_university_name = models.CharField(
        _("Зарубежный ОТМ, присвоивший степень"), max_length=255, blank=True,
    )
    hire_order_number = models.CharField(_("№ приказа о приёме"), max_length=50, blank=True)
    hire_order_date = models.DateField(_("Дата приказа о приёме"), null=True, blank=True)
    hire_order_file = models.FileField(
        _("Скан приказа о приёме (PDF)"), upload_to="teachers/orders/",
        null=True, blank=True, validators=DOCUMENT_VALIDATORS,
    )

    # --- Лист 1,3: степень / магистратура из зарубежного ОТМ ------------------
    foreign_degree_rank = models.CharField(
        _("Рейтинг зарубежного ОТМ, присвоившего степень"), max_length=10,
        choices=ForeignInstitutionRank.choices, blank=True,
        help_text=_("Заполняется, только если степень получена за рубежом."),
    )
    foreign_master_university = models.CharField(
        _("Зарубежный ОТМ, где окончена магистратура"), max_length=255, blank=True,
    )
    foreign_master_rank = models.CharField(
        _("Рейтинг зарубежного ОТМ (магистратура)"), max_length=10,
        choices=ForeignInstitutionRank.choices, blank=True,
    )
    master_diploma_file = models.FileField(
        _("Скан зарубежного диплома магистра (PDF)"), upload_to="teachers/master_diplomas/",
        null=True, blank=True, validators=DOCUMENT_VALIDATORS,
    )

    # --- Лист 1,4: иностранные преподаватели ------------------------------------
    is_foreign_citizen = models.BooleanField(_("Иностранный гражданин"), default=False)
    citizenship_country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="teachers", verbose_name=_("Гражданство (для иностранцев)"),
    )

    is_active = models.BooleanField(_("Работает сейчас"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Преподаватель")
        verbose_name_plural = _("Преподаватели")
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    def age_on(self, on_date=None):
        if not self.birth_date:
            return None
        on_date = on_date or date.today()
        return on_date.year - self.birth_date.year - (
            (on_date.month, on_date.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def age(self):
        return self.age_on()

    @property
    def hire_order_display(self):
        if not self.hire_order_number:
            return ""
        if self.hire_order_date:
            return f"{self.hire_order_number}, {self.hire_order_date:%d.%m.%Y}"
        return self.hire_order_number


class TeacherPeriodSnapshot(models.Model):
    """
    Снимок статуса преподавателя на конкретный отчётный период — покрывает
    5-jadval (штатная ведомость): тип занятости, должность, ставка, степень
    и звание могут отличаться от периода к периоду.
    """

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="period_snapshots",
        verbose_name=_("Преподаватель"),
    )
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.CASCADE, related_name="teacher_snapshots",
        verbose_name=_("Отчётный период"),
    )
    employment_type = models.ForeignKey(
        EmploymentType, on_delete=models.PROTECT, verbose_name=_("Тип занятости"),
    )
    position = models.ForeignKey(
        Position, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("Должность"),
    )
    stavka = models.DecimalField(_("Ставка"), max_digits=4, decimal_places=2, default=1)
    academic_degree = models.ForeignKey(
        AcademicDegree, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Учёная степень на момент отчёта"),
    )
    academic_title = models.ForeignKey(
        AcademicTitle, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Учёное звание на момент отчёта"),
    )

    class Meta:
        verbose_name = _("Снимок статуса ППС за период")
        verbose_name_plural = _("Снимки статуса ППС за период")
        unique_together = [("teacher", "reporting_period")]
        ordering = ["reporting_period", "employment_type__sort_order", "teacher__full_name"]

    def __str__(self):
        return f"{self.teacher} — {self.reporting_period}"
