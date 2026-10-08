from django import forms
from django.forms import modelform_factory
from django.utils.translation import gettext_lazy as _

from apps.staff.models import Teacher
from apps.workflow.models import ReportingPeriod

DATE_FIELDS = {"issue_date", "defense_date", "start_date", "end_date", "hire_order_date", "birth_date"}


def _widgets(fields):
    widgets = {"reporting_period": forms.Select}
    for name in fields:
        if name in DATE_FIELDS:
            widgets[name] = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    return widgets


class CoauthoredMixin:
    """Список соавторов-сотрудников кафедры и проверка «N не меньше числа
    отмеченных авторов кафедры» для статей и патентов."""

    def setup_coauthors(self, teacher):
        self.teacher = teacher
        self.fields["coauthors"] = forms.ModelMultipleChoiceField(
            label=_("Соавторы с нашей кафедры"),
            help_text=_("Отметьте коллег-соавторов: запись появится и в их кабинетах, "
                        "каждому будет засчитана доля 1/N."),
            queryset=Teacher.objects.filter(department=teacher.department, is_active=True)
            .exclude(pk=teacher.pk),
            required=False,
            widget=forms.CheckboxSelectMultiple,
        )
        if self.instance.pk:
            self.initial["coauthors"] = list(
                self.instance.authors.exclude(pk=teacher.pk).values_list("pk", flat=True)
            )
        self.fields["authors_total"].required = True
        # соавторы — сразу после поля «общее число авторов»
        order = list(self.fields)
        order.remove("coauthors")
        order.insert(order.index("authors_total") + 1, "coauthors")
        self.order_fields(order)

    def clean(self):
        data = super().clean()
        total = data.get("authors_total")
        dept_authors = 1 + len(data.get("coauthors") or [])
        if total is not None and total < dept_authors:
            self.add_error("authors_total", _(
                "Общее число авторов не может быть меньше числа отмеченных авторов кафедры (%(n)s)."
            ) % {"n": dept_authors})
        return data

    def save_authors(self, obj):
        authors = {self.teacher, *self.cleaned_data.get("coauthors", [])}
        # соавторов из других кабинетов, которых этот преподаватель не видит
        # в списке (например, уволившихся), не выкидываем
        hidden = set(obj.authors.exclude(pk__in=self.fields["coauthors"].queryset).exclude(pk=self.teacher.pk))
        obj.authors.set(authors | hidden)


def build_form_class(cfg):
    base = (CoauthoredMixin, forms.ModelForm) if cfg.get("authors") else (forms.ModelForm,)
    form_base = type("RegistryBaseForm", base, {})
    return modelform_factory(cfg["model"], form=form_base, fields=cfg["fields"],
                             widgets=_widgets(cfg["fields"]))


def open_periods(teacher):
    return ReportingPeriod.objects.filter(
        department=teacher.department, status=ReportingPeriod.Status.DRAFT,
    ).order_by("-period_date")


class TeacherProfileForm(forms.ModelForm):
    """Преподаватель сам вносит данные о себе для листов 1,1–1,4: дата
    рождения, диплом об учёной степени, приказ о приёме, зарубежные дипломы,
    гражданство. Ставку, должность, тип занятости и степень/звание за
    конкретный период (штатная ведомость, лист «5») задаёт кафедра в
    админ-панели — это кадровые данные."""

    class Meta:
        model = Teacher
        fields = [
            "birth_date",
            "specialty_name", "diploma_series", "diploma_number", "diploma_file",
            "foreign_university_name", "foreign_degree_rank",
            "hire_order_number", "hire_order_date", "hire_order_file",
            "foreign_master_university", "foreign_master_rank", "master_diploma_file",
            "is_foreign_citizen", "citizenship_country",
        ]
        widgets = _widgets(fields)

    SECTIONS = [
        (_("Личные данные (лист 1,2)"), ["birth_date"]),
        (_("Диплом об учёной степени / звании (лист 1,1)"), [
            "specialty_name", "diploma_series", "diploma_number", "diploma_file",
            "foreign_university_name", "foreign_degree_rank",
        ]),
        (_("Приказ о приёме на работу (лист 1,1)"), ["hire_order_number", "hire_order_date", "hire_order_file"]),
        (_("Зарубежная магистратура (лист 1,3)"), [
            "foreign_master_university", "foreign_master_rank", "master_diploma_file",
        ]),
        (_("Гражданство (лист 1,4)"), ["is_foreign_citizen", "citizenship_country"]),
    ]

    def sections(self):
        for title, names in self.SECTIONS:
            yield title, [self[name] for name in names]
