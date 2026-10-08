from django.db import models
from django.utils.translation import gettext_lazy as _


class EmploymentType(models.Model):
    """asosiy shtat / ichki o'rindosh / tashqi o'rindosh / soatbay."""

    ASOSIY = "asosiy"
    ICHKI = "ichki_orindosh"
    TASHQI = "tashqi_orindosh"
    SOATBAY = "soatbay"

    code = models.CharField(_("Код"), max_length=30, unique=True)
    name = models.CharField(_("Название"), max_length=100)
    sort_order = models.PositiveSmallIntegerField(_("Порядок в отчёте"), default=0)

    class Meta:
        verbose_name = _("Тип занятости")
        verbose_name_plural = _("Типы занятости")
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField(_("Название должности"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("Должность (лавозим)")
        verbose_name_plural = _("Должности (лавозимлар)")
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicDegree(models.Model):
    """Fan nomzodi / PhD / Fan doktori / DSc."""

    code = models.CharField(_("Код"), max_length=20, unique=True)
    name = models.CharField(_("Название"), max_length=100)

    class Meta:
        verbose_name = _("Учёная степень")
        verbose_name_plural = _("Учёные степени")
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicTitle(models.Model):
    """Dotsent / Professor."""

    name = models.CharField(_("Название"), max_length=100, unique=True)

    class Meta:
        verbose_name = _("Учёное звание")
        verbose_name_plural = _("Учёные звания")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Country(models.Model):
    class Category(models.TextChoices):
        HIGH_INCOME = "high_income_developed", _("Развитая страна с высоким доходом (список Всемирного банка)")
        CENTRAL_ASIA = "central_asia", _("Страна Центральной Азии")
        OTHER = "other", _("Другая страна")

    name = models.CharField(_("Название страны"), max_length=100, unique=True)
    category = models.CharField(
        _("Категория (для отчётов по мобильности)"), max_length=30,
        choices=Category.choices, default=Category.OTHER,
    )
    is_home_country = models.BooleanField(
        _("Страна вуза (Узбекистан)"), default=False,
        help_text=_("Студенты и преподаватели с этим гражданством не считаются иностранцами."),
    )

    class Meta:
        verbose_name = _("Страна")
        verbose_name_plural = _("Страны")
        ordering = ["name"]

    def __str__(self):
        return self.name


class ForeignInstitutionRank(models.TextChoices):
    """TOP-100 / TOP-300 / TOP-500 / TOP-1000 / вне рейтинга — повторяется
    в нескольких листах (мобильность, совместные программы, зарубежные
    степени), поэтому вынесено в общий справочник-перечисление."""

    TOP100 = "TOP100", "TOP-100"
    TOP300 = "TOP300", "TOP-300"
    TOP500 = "TOP500", "TOP-500"
    TOP1000 = "TOP1000", "TOP-1000"
    OTHER = "other", _("Вне рейтинга TOP-1000")
