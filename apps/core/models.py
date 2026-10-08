from django.db import models
from django.utils.translation import gettext_lazy as _


class University(models.Model):
    name = models.CharField(_("Название (полное)"), max_length=255)
    short_name = models.CharField(_("Короткое название"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("Университет")
        verbose_name_plural = _("Университеты")
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name


class Faculty(models.Model):
    university = models.ForeignKey(
        University, on_delete=models.PROTECT, related_name="faculties",
        verbose_name=_("Университет"),
    )
    name = models.CharField(_("Название факультета"), max_length=255)
    short_name = models.CharField(_("Короткое название"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("Факультет")
        verbose_name_plural = _("Факультеты")
        ordering = ["name"]
        unique_together = [("university", "name")]

    def __str__(self):
        return self.short_name or self.name


class Department(models.Model):
    """
    Единая сущность «кафедра». Намеренно только одна таблица — в исходной
    ERD-схеме вуза кафедра была продублирована как departments и kafedralar
    с неочевидной связью между ними; здесь эта путаница устранена.
    """

    faculty = models.ForeignKey(
        Faculty, on_delete=models.PROTECT, related_name="departments",
        verbose_name=_("Факультет"),
    )
    name = models.CharField(_("Название кафедры"), max_length=255)
    short_name = models.CharField(_("Короткое название"), max_length=50, blank=True)

    class Meta:
        verbose_name = _("Кафедра")
        verbose_name_plural = _("Кафедры")
        ordering = ["name"]
        unique_together = [("faculty", "name")]

    def __str__(self):
        return self.short_name or self.name
