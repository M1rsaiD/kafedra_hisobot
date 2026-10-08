"""
Факт-таблицы показателей кафедры. Общий принцип для всех таблиц этого файла:

- они хранят АТОМАРНЫЕ факты (одна публикация, один патент, один голос
  эксперта), а не готовые суммы — итоговые "Jami" в отчёте считаются
  агрегирующим запросом (SUM/COUNT) в apps/exporter, а не хранятся полем;
- почти каждая факт-таблица ссылается на ReportingPeriod — это и есть та
  «шина», вокруг которой построена вся схема: один и тот же список
  показателей можно вести из периода в период, не переписывая историю;
- у каждого раздела есть поле для подтверждающего документа — эти файлы
  выгружаются отдельным ZIP-архивом по папкам разделов (apps/exporter/archive.py);
- статья и патент/свидетельство — общие записи с несколькими авторами
  кафедры: каждому засчитывается доля 1/N, где N — общее число авторов
  (authors_total). Два автора — по 0.5, три — по 0.33.
- IndicatorValue — универсальный запасной вариант на случай, если
  министерство добавит новый показатель, под который ещё не заведена
  отдельная таблица: не требует миграции схемы.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.validators import DOCUMENT_VALIDATORS
from apps.dictionaries.models import ForeignInstitutionRank
from apps.staff.models import Teacher
from apps.students.models import Student, Graduate
from apps.workflow.models import ReportingPeriod


class AuthorShareMixin:
    """Доля одного автора-сотрудника кафедры в общей работе = 1/N.

    N — общее число авторов (authors_total), включая авторов из других
    организаций. Если N не указано, делим поровну между отмеченными
    авторами кафедры (это минимально возможное N)."""

    def author_share(self):
        n = max(self.authors_total or 0, self.department_authors_count()) or 1
        return Decimal(1) / Decimal(n)

    def department_authors_count(self):
        # при prefetch_related("authors") не делаем лишний запрос
        cache = getattr(self, "_prefetched_objects_cache", {})
        if "authors" in cache:
            return len(cache["authors"])
        return self.authors.count()

    def author_share_display(self):
        return self.author_share().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Publication(AuthorShareMixin, models.Model):
    class Quartile(models.TextChoices):
        Q1 = "Q1", "Q1"
        Q2 = "Q2", "Q2"
        Q3 = "Q3", "Q3"
        Q4 = "Q4", "Q4"

    class CitationTier(models.TextChoices):
        TOP1 = "top1", "Top 1% most cited"
        TOP10 = "top10", "Top 10% most cited"

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="entered_publications",
        verbose_name=_("Кто внёс запись"),
    )
    authors = models.ManyToManyField(
        Teacher, through="PublicationAuthor", related_name="publications",
        verbose_name=_("Авторы — сотрудники кафедры"),
    )
    authors_total = models.PositiveSmallIntegerField(
        _("Общее число авторов статьи"), null=True, blank=True,
        help_text=_("Включая авторов из других организаций. Каждому автору кафедры "
                    "засчитывается доля 1/N: при 2 авторах — по 0.5, при 3 — по 0.33."),
    )
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="publications", verbose_name=_("Отчётный период"))
    journal_name = models.CharField(_("Название журнала"), max_length=255, blank=True)
    publish_year = models.PositiveSmallIntegerField(_("Год публикации"), null=True, blank=True)
    publish_month = models.PositiveSmallIntegerField(_("Месяц публикации"), null=True, blank=True)
    article_title = models.CharField(_("Название статьи"), max_length=500, blank=True)
    language = models.CharField(_("Язык публикации"), max_length=30, blank=True)
    scopus_url = models.URLField(_("Ссылка Scopus"), max_length=500, blank=True)
    quartile = models.CharField(_("Квартиль"), max_length=2, choices=Quartile.choices, null=True, blank=True)
    citation_tier = models.CharField(_("Топ по цитируемости"), max_length=10, choices=CitationTier.choices, null=True, blank=True)
    citations_count = models.PositiveIntegerField(_("Число цитирований (Scopus)"), default=0)
    article_file = models.FileField(
        _("Электронный PDF статьи"), upload_to="publications/", null=True, blank=True,
        validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Публикация (Scopus)")
        verbose_name_plural = _("Публикации (Scopus)")
        ordering = ["-publish_year", "-publish_month"]

    def __str__(self):
        return self.article_title[:60] or f"#{self.pk}"


class PublicationAuthor(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name=_("Преподаватель"))

    class Meta:
        verbose_name = _("Автор статьи")
        verbose_name_plural = _("Авторы статьи")
        unique_together = [("publication", "teacher")]


class TeacherHIndex(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="hindex_records", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="hindex_records", verbose_name=_("Отчётный период"))
    h_index = models.PositiveIntegerField(_("Индекс Хирша (Scopus)"))
    scopus_profile_url = models.URLField(_("Ссылка на профиль Scopus"), max_length=500, blank=True)
    document_file = models.FileField(
        _("Скриншот профиля Scopus (PDF/PNG)"), upload_to="hindex/", null=True, blank=True,
        validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("H-индекс")
        verbose_name_plural = _("H-индексы")
        unique_together = [("teacher", "reporting_period")]

    def __str__(self):
        return f"{self.teacher}: h={self.h_index}"


class Patent(AuthorShareMixin, models.Model):
    class PatentType(models.TextChoices):
        INVENTION = "invention", _("Изобретение")
        UTILITY_MODEL = "utility_model", _("Полезная модель")
        INDUSTRIAL_DESIGN = "industrial_design", _("Промышленный образец")
        SELECTION = "selection_achievement", _("Селекционное достижение")
        SOFTWARE = "software_certificate", _("Свидетельство на программу/БД (DGU)")

    # Виды, которые форма 2,4 считает патентами. Свидетельства DGU хранятся
    # и уходят в архив, но в 2,4 не засчитываются (их там нет в заголовке).
    SHEET_2_4_TYPES = (
        PatentType.INVENTION, PatentType.UTILITY_MODEL,
        PatentType.INDUSTRIAL_DESIGN, PatentType.SELECTION,
    )

    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="patents", verbose_name=_("Отчётный период"))
    title = models.CharField(_("Название"), max_length=500, blank=True)
    patent_type = models.CharField(_("Тип"), max_length=30, choices=PatentType.choices)
    number = models.CharField(_("Номер патента / свидетельства"), max_length=50, blank=True)
    issue_date = models.DateField(_("Дата выдачи"), null=True, blank=True)
    authors_total = models.PositiveSmallIntegerField(
        _("Общее число авторов"), null=True, blank=True,
        help_text=_("Включая авторов из других организаций. Каждому автору кафедры "
                    "засчитывается доля 1/N."),
    )
    registered_in_scopus = models.BooleanField(_("Учтён в Scopus"), default=False)
    has_license_agreement = models.BooleanField(_("Есть лицензионный договор"), default=False)
    document_file = models.FileField(
        _("Документ, подтверждающий патент (PDF)"), upload_to="patents/", null=True, blank=True,
        validators=DOCUMENT_VALIDATORS,
    )
    authors = models.ManyToManyField(Teacher, through="PatentAuthor", related_name="patents", verbose_name=_("Авторы — сотрудники кафедры"))

    class Meta:
        verbose_name = _("Патент / свидетельство")
        verbose_name_plural = _("Патенты / свидетельства")

    def __str__(self):
        return self.title or f"#{self.pk}"


class PatentAuthor(models.Model):
    patent = models.ForeignKey(Patent, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, verbose_name=_("Преподаватель"))

    class Meta:
        verbose_name = _("Автор патента")
        verbose_name_plural = _("Авторы патента")
        unique_together = [("patent", "teacher")]


class Funding(models.Model):
    class SourceType(models.TextChoices):
        FOREIGN = "foreign_international", _("Зарубежные / международные организации")
        STATE_PROGRAM = "state_program", _("Государственные научные программы")
        BUSINESS_CONTRACT = "business_contract", _("Хоздоговорные заказы")

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="fundings", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="fundings", verbose_name=_("Отчётный период"))
    source_type = models.CharField(_("Источник средств"), max_length=30, choices=SourceType.choices)
    amount = models.DecimalField(_("Сумма (сум)"), max_digits=15, decimal_places=2)
    contract_info = models.CharField(
        _("Договор / приказ: номер, дата, заказчик"), max_length=500, blank=True,
    )
    document_file = models.FileField(
        _("Договор / квитанция (PDF)"), upload_to="fundings/", null=True, blank=True,
        validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Привлечённые средства")
        verbose_name_plural = _("Привлечённые средства")

    def __str__(self):
        return f"{self.teacher} — {self.amount}"


class PostgradDefense(models.Model):
    class DegreeType(models.TextChoices):
        PHD = "PhD", _("PhD (доктор философии)")
        DSC = "DSc", _("DSc (доктор наук)")

    advisor_teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="postgrad_defenses", verbose_name=_("Научный руководитель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="postgrad_defenses", verbose_name=_("Отчётный период"))
    degree_type = models.CharField(_("Степень"), max_length=5, choices=DegreeType.choices)
    defended_full_name = models.CharField(_("Ф.И.Ш. соискателя"), max_length=255, blank=True)
    defense_date = models.DateField(_("Дата защиты"), null=True, blank=True)
    document_file = models.FileField(
        _("Подтверждающий документ (протокол / диплом, PDF)"), upload_to="defenses/",
        null=True, blank=True, validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Защита диссертации (под руководством)")
        verbose_name_plural = _("Защиты диссертаций (под руководством)")

    def __str__(self):
        return f"{self.advisor_teacher} — {self.degree_type}"


class ReputationVote(models.Model):
    class Source(models.TextChoices):
        RATING_ORG = "rating_org_expert", _("Эксперт THE / QS / ARWU")
        NATIONAL_QA = "national_qa_agency_expert", _("Эксперт нац. агентства по качеству образования")
        FOREIGN_PARTNER = "foreign_partner_staff", _("Сотрудник зарубежного вуза-партнёра")

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="reputation_votes", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="reputation_votes", verbose_name=_("Отчётный период"))
    source = models.CharField(_("Источник голосов"), max_length=30, choices=Source.choices)
    votes_count = models.PositiveIntegerField(_("Число голосов"))
    note = models.CharField(_("Примечание (организация, респонденты)"), max_length=500, blank=True)
    document_file = models.FileField(
        _("Список респондентов / подтверждение (PDF, Excel)"), upload_to="reputation/",
        null=True, blank=True, validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Голос за международную репутацию")
        verbose_name_plural = _("Голоса за международную репутацию")

    def __str__(self):
        return f"{self.teacher} — {self.source}: {self.votes_count}"


class TeacherMobility(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = "outbound", _("Outbound (выезд за рубеж)")
        INBOUND = "inbound", _("Inbound (приём зарубежного преподавателя)")

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="mobility_records", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="teacher_mobility", verbose_name=_("Отчётный период"))
    direction = models.CharField(_("Направление"), max_length=10, choices=Direction.choices)
    partner_institution_name = models.CharField(_("Партнёрский вуз"), max_length=255, blank=True)
    start_date = models.DateField(_("Начало"), null=True, blank=True)
    end_date = models.DateField(_("Окончание"), null=True, blank=True)
    order_info = models.CharField(_("Приказ ректора: номер и дата"), max_length=255, blank=True)
    document_file = models.FileField(
        _("Приказ / сертификат (PDF)"), upload_to="mobility/", null=True, blank=True,
        validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Международная мобильность ППС")
        verbose_name_plural = _("Международная мобильность ППС")

    def __str__(self):
        return f"{self.teacher} — {self.direction}"


class StudentMobility(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = "outbound", "Outbound"
        INBOUND = "inbound", "Inbound"

    class ProgramType(models.TextChoices):
        EXCHANGE = "exchange", _("Программа обмена (лист 3,3)")
        JOINT_PROGRAM = "joint_program", _("Совместная образовательная программа (лист 3,5)")

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="mobility_records", verbose_name=_("Студент"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="student_mobility", verbose_name=_("Отчётный период"))
    direction = models.CharField(_("Направление"), max_length=10, choices=Direction.choices, blank=True)
    program_type = models.CharField(_("Тип программы"), max_length=20, choices=ProgramType.choices)
    partner_institution_name = models.CharField(_("Партнёрский вуз"), max_length=255, blank=True)
    partner_rank = models.CharField(
        _("Рейтинг партнёрского вуза"), max_length=10, choices=ForeignInstitutionRank.choices,
    )
    order_info = models.CharField(_("Приказ ректора: номер и дата"), max_length=255, blank=True)
    document_file = models.FileField(
        _("Приказ / подтверждение (PDF)"), upload_to="student_mobility/", null=True, blank=True,
        validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Академическая мобильность студента")
        verbose_name_plural = _("Академическая мобильность студентов")

    def __str__(self):
        return f"{self.student} — {self.partner_rank}"


class GraduateEmployment(models.Model):
    class Status(models.TextChoices):
        ENTREPRENEUR = "entrepreneur_or_founder", _("ИП / учредитель")
        EMPLOYED = "employed_state_or_business", _("Трудоустроен (гос. орган / хоз. субъект)")
        EXEMPT = "further_education_or_exempt", _("Продолжает учёбу / декрет / инвалидность / самозанят")

    graduate = models.OneToOneField(Graduate, on_delete=models.CASCADE, related_name="employment", verbose_name=_("Выпускник"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="graduate_employment", verbose_name=_("Отчётный период"))
    status = models.CharField(_("Статус занятости"), max_length=30, choices=Status.choices)
    months_to_employment = models.PositiveSmallIntegerField(
        _("Через сколько месяцев трудоустроен"), null=True, blank=True,
        choices=[(3, "3"), (6, "6"), (12, "12")],
    )
    monthly_income = models.DecimalField(_("Средний месячный доход"), max_digits=12, decimal_places=2, null=True, blank=True)
    document_file = models.FileField(
        _("Справка с места работы (PDF)"), upload_to="graduates/", null=True, blank=True,
        validators=DOCUMENT_VALIDATORS,
    )

    class Meta:
        verbose_name = _("Трудоустройство выпускника")
        verbose_name_plural = _("Трудоустройство выпускников")

    def __str__(self):
        return f"{self.graduate} — {self.status}"


class NationalAvgSalary(models.Model):
    """Справочная величина Госкомстата — не факт о выпускнике, а точка
    сравнения для листа «Bitiruvchilarning o'rtacha daromadi»."""

    year = models.PositiveSmallIntegerField(_("Год"))
    month = models.PositiveSmallIntegerField(_("Месяц"))
    amount = models.DecimalField(_("Средняя номинальная зарплата по РУз"), max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = _("Средняя зарплата по стране (Госкомстат)")
        verbose_name_plural = _("Средняя зарплата по стране (Госкомстат)")
        unique_together = [("year", "month")]
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.year}-{self.month:02d}: {self.amount}"


class IndicatorValue(models.Model):
    """
    Универсальный запасной вариант для показателей, под которые ещё нет
    отдельной таблицы (методика рейтинга вузов Узбекистана пересматривается
    почти ежегодно). Не заменяет таблицы выше — используется только для
    новых/редких пунктов, чтобы не делать миграцию схемы под каждое
    изменение методики.
    """

    class SubjectType(models.TextChoices):
        TEACHER = "teacher", _("Преподаватель")
        STUDENT = "student", _("Студент")
        GRADUATE = "graduate", _("Выпускник")
        DEPARTMENT = "department", _("Кафедра")

    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="indicator_values", verbose_name=_("Отчётный период"))
    subject_type = models.CharField(_("Тип субъекта"), max_length=20, choices=SubjectType.choices)
    subject_id = models.PositiveIntegerField(_("ID субъекта"))
    indicator_code = models.CharField(_("Код показателя"), max_length=100, help_text=_("Например: sheet_1_3_top100_degree_count"))
    value_numeric = models.DecimalField(_("Числовое значение"), max_digits=15, decimal_places=2, null=True, blank=True)
    value_text = models.CharField(_("Текстовое значение"), max_length=500, blank=True)
    document_path = models.CharField(_("Путь к подтверждающему документу"), max_length=500, blank=True)

    class Meta:
        verbose_name = _("Показатель (гибкий, вне основной схемы)")
        verbose_name_plural = _("Показатели (гибкие, вне основной схемы)")
        unique_together = [("reporting_period", "subject_type", "subject_id", "indicator_code")]

    def __str__(self):
        return f"{self.indicator_code} [{self.subject_type}#{self.subject_id}]"
