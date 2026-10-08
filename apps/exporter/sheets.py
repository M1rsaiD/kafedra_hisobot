"""
Заполнение всех 20 листов формы «Umumiy kafedra reytingi» (редакция 2026).

Каждая функция fill_<лист>(writer, data) получает BodyWriter (см. layout.py),
который уже очистил тело листа, и ReportData — заранее загруженные данные
периода. Функция пишет секции/строки/итог, подвал (примечание и подпись
«Rektor») BodyWriter переносит сам. Поэтому число строк не ограничено
шаблоном: сколько людей/статей — столько и строк.

Колонки ниже соответствуют шапкам листов формы 2026 (см. LAYOUTS).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

from django.utils.translation import gettext as _

from apps.dictionaries.models import Country, ForeignInstitutionRank as Rank
from apps.reports.models import (
    Publication, TeacherHIndex, Patent, Funding, PostgradDefense, ReputationVote,
    TeacherMobility, StudentMobility, GraduateEmployment, NationalAvgSalary,
)
from apps.staff.models import TeacherPeriodSnapshot
from apps.students.models import Student

from .layout import SheetLayout

ASOSIY = "asosiy"
ICHKI = "ichki_orindosh"
TASHQI = "tashqi_orindosh"
SOATBAY = "soatbay"

# Секции листов 1,1 / 1,2 / 2,3 / 2,4 (тексты — как в форме 2026)
TEACHER_SECTIONS = [(ASOSIY, "Asosiy shtatdagilar"), (ICHKI, "Ichki o‘rindosh")]

# Секции листа 5
STAFFING_SECTIONS = [
    (ASOSIY, "Asosiy shtatdagi FISH (alfavit tartibida to‘liq yoziladi)."),
    (ICHKI, "Ichki o‘rindoshlar (rektor, prorektor, dekan, dekan o‘rinbosarlari, kafedra mudiri "
            "va boshqalar) FISH (alfavit tartibida to‘liq yoziladi)."),
    (TASHQI, "Tashqi o‘rindosh o‘qituvchilarning FISH (alfavit tartibida to‘liq yoziladi)."),
    (SOATBAY, "Soatbay o‘qituvchilarning FISH (alfavit tartibida to‘liq yoziladi)."),
]

LAYOUTS = {
    "1,1": SheetLayout(header_rows=3, ncols=11, has_marker=True, has_total=False),
    "1,2": SheetLayout(header_rows=2, ncols=4, has_marker=True),
    "1,3": SheetLayout(header_rows=2, ncols=7),
    "1,4": SheetLayout(header_rows=2, ncols=8),
    "2,1": SheetLayout(header_rows=2, ncols=8),
    "2,2": SheetLayout(header_rows=2, ncols=8),
    "2,3": SheetLayout(header_rows=2, ncols=3, has_marker=True),
    "2,4": SheetLayout(header_rows=2, ncols=4, has_marker=True),
    "2,5": SheetLayout(header_rows=2, ncols=3),
    "2,6": SheetLayout(header_rows=2, ncols=5),
    "2,7": SheetLayout(header_rows=2, ncols=4),
    "3,1": SheetLayout(header_rows=2, ncols=5),
    "3,2": SheetLayout(header_rows=2, ncols=6),
    "3,3": SheetLayout(header_rows=2, ncols=7),
    "3,4": SheetLayout(header_rows=2, ncols=4),
    "3,5": SheetLayout(header_rows=2, ncols=7),
    "4,1": SheetLayout(header_rows=2, ncols=5),
    "4,2": SheetLayout(header_rows=2, ncols=6),
    "4,3": SheetLayout(header_rows=2, ncols=4),
    "5": SheetLayout(header_rows=5, ncols=7, has_marker=True, marker_col=2, has_total=False),
}

JAMI = "Jami:"


def num(value):
    """Decimal/float → int, если целое, иначе округление до 0.01 (как доли 0.33/0.5)."""
    if value is None:
        return None
    value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value == 0:
        return None
    return int(value) if value == value.to_integral_value() else float(value)


def total_of(rows, col):
    vals = [Decimal(str(r[col])) for r in rows if isinstance(r.get(col), (int, float, Decimal))]
    return num(sum(vals)) if vals else None


@dataclass
class ReportData:
    """Всё, что нужно листам, загружается один раз на период."""

    period: object
    snapshots: dict = field(default_factory=dict)      # code -> [snapshot]
    snap_by_teacher: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    @classmethod
    def load(cls, period):
        data = cls(period=period)
        qs = (
            TeacherPeriodSnapshot.objects.filter(reporting_period=period)
            .select_related("teacher", "teacher__citizenship_country", "employment_type",
                            "position", "academic_degree", "academic_title")
            .order_by("teacher__full_name")
        )
        for snap in qs:
            data.snapshots.setdefault(snap.employment_type.code, []).append(snap)
            data.snap_by_teacher[snap.teacher_id] = snap
        return data

    def staff(self, codes=(ASOSIY, ICHKI)):
        out = []
        for code in codes:
            out.extend(self.snapshots.get(code, []))
        return sorted(out, key=lambda s: s.teacher.full_name)

    def in_report(self, teacher, sheet, what):
        """Показатели листов 1–3 учитываются только для основного штата и
        внутренних совместителей. Если запись есть, а снимка в штатной
        ведомости нет — запись не потеряется молча, а попадёт в предупреждения."""
        snap = self.snap_by_teacher.get(teacher.id)
        if snap and snap.employment_type.code in (ASOSIY, ICHKI):
            return True
        reason = (_("нет в штатной ведомости периода") if snap is None
                  else _("тип занятости «%(type)s»") % {"type": snap.employment_type})
        self.warnings.append(_("%(sheet)s: %(name)s — %(what)s не учтено (%(reason)s)") % {
            "sheet": sheet, "name": teacher.full_name, "what": what, "reason": reason})
        return False


def _data_rows(writer, rows, empty_placeholder=True):
    for i, values in enumerate(rows, start=1):
        writer.data({1: i, **values})
    if not rows and empty_placeholder:
        writer.data({})


def _sectioned(writer, data, build_row, include=lambda snap: True, sections=TEACHER_SECTIONS,
               always_marker=False):
    rows_all = []
    for code, title in sections:
        snaps = [s for s in data.snapshots.get(code, []) if include(s)]
        if not snaps and not always_marker:
            continue
        writer.marker(title)
        for i, snap in enumerate(snaps, start=1):
            values = {1: i, 2: snap.teacher.full_name, **build_row(snap)}
            writer.data(values)
            rows_all.append(values)
    if not rows_all and not always_marker:
        writer.data({})
    return rows_all


# --- 1,1 — Ilmiy daraja (unvon)ga ega PO' ulushi ------------------------------
# A T/r, B FISH, C xorijiy OTM, D-E akademik (seriya/raqam), F-G DSc/professor,
# H-I PhD/dotsent, J mutaxassislik, K ishga qabul buyrug'i
def _degree_columns(snap):
    code = (snap.academic_degree.code if snap.academic_degree else "").lower()
    if code == "akademik":
        return 4, 5
    if code in ("dsc", "fan_doktori"):
        return 6, 7
    if code in ("phd", "fan_nomzodi"):
        return 8, 9
    title = (snap.academic_title.name if snap.academic_title else "").lower()
    if "prof" in title:
        return 6, 7
    if "dots" in title or "доц" in title:
        return 8, 9
    return None


def fill_1_1(writer, data):
    def row(snap):
        t = snap.teacher
        values = {3: t.foreign_university_name or None, 10: t.specialty_name or None,
                  11: t.hire_order_display or None}
        cols = _degree_columns(snap)
        if cols and (t.diploma_series or t.diploma_number):
            values[cols[0]] = t.diploma_series or None
            values[cols[1]] = t.diploma_number or None
        return values

    _sectioned(writer, data, row, include=lambda s: s.academic_degree_id or s.academic_title_id)


# --- 1,2 — ilmiy darajaga ega PO' o'rtacha yoshi -------------------------------
def fill_1_2(writer, data):
    on = data.period.period_date

    def row(snap):
        t = snap.teacher
        if not t.birth_date:
            data.warnings.append(_("1,2: %(name)s — не указана дата рождения") % {"name": t.full_name})
        return {3: t.birth_date, 4: t.age_on(on)}

    rows = _sectioned(writer, data, row, include=lambda s: s.academic_degree_id)
    ages = [r[4] for r in rows if r.get(4) is not None]
    writer.total({2: "O‘rtacha yosh:", 4: num(Decimal(sum(ages)) / len(ages)) if ages else None})


# --- 1,3 — xorijiy OTMda olingan daraja / magistratura ----------------------------
DEGREE_RANK_COL = {Rank.TOP100: 3, Rank.TOP300: 4, Rank.TOP500: 5, Rank.TOP1000: 6}


def fill_1_3(writer, data):
    rows = []
    for snap in data.staff():
        t = snap.teacher
        values = {}
        if t.foreign_degree_rank in DEGREE_RANK_COL:
            values[DEGREE_RANK_COL[t.foreign_degree_rank]] = 1
        if t.foreign_master_rank in (Rank.TOP100, Rank.TOP300):
            values[7] = 1
        if values:
            rows.append({2: t.full_name, **values})
    _data_rows(writer, rows)
    writer.total({2: JAMI, **{c: total_of(rows, c) for c in range(3, 8)}})


# --- 1,4 — xorijiy PO' ------------------------------------------------------------
# C yuqori daromadli mamlakat fuqarosi, D TOP-500 dan daraja, E (E:F) boshqa xorijiy
# OTM dan daraja, G (G:H) buyruq, sana, fan
def fill_1_4(writer, data):
    rows = []
    for snap in data.staff():
        t = snap.teacher
        if not t.is_foreign_citizen:
            continue
        values = {2: t.full_name}
        if t.citizenship_country and t.citizenship_country.category == Country.Category.HIGH_INCOME:
            values[3] = 1
        if t.foreign_degree_rank in (Rank.TOP100, Rank.TOP300, Rank.TOP500):
            values[4] = 1
        elif t.foreign_degree_rank or t.foreign_university_name:
            values[5] = 1
        values[7] = "; ".join(x for x in [t.hire_order_display, t.specialty_name] if x) or None
        rows.append(values)
    _data_rows(writer, rows)
    writer.total({2: JAMI, 3: total_of(rows, 3), 4: total_of(rows, 4), 5: total_of(rows, 5)})


# --- 2,1 — Scopus maqolalari kvartillar bo'yicha (ulush 1/N) ----------------------
def _publications(data):
    if not hasattr(data, "_pubs"):
        data._pubs = list(
            Publication.objects.filter(reporting_period=data.period)
            .prefetch_related("authors").order_by("-publish_year", "-publish_month", "id")
        )
    return data._pubs


def fill_2_1(writer, data):
    year = data.period.period_date.year
    sums = defaultdict(lambda: defaultdict(Decimal))
    teachers = {}
    for pub in _publications(data):
        if pub.publish_year and pub.publish_year != year:
            continue  # в 2,1 — только статьи, индексированные в году отчёта
        share = pub.author_share()
        for author in pub.authors.all():
            if not data.in_report(author, "2,1", _("статья «%(t)s»") % {"t": pub.article_title[:40]}):
                continue
            teachers[author.id] = author
            bucket = sums[author.id]
            if pub.citation_tier == Publication.CitationTier.TOP1:
                bucket[3] += share
            elif pub.citation_tier == Publication.CitationTier.TOP10:
                bucket[4] += share
            if pub.quartile:
                bucket[{"Q1": 5, "Q2": 6, "Q3": 7, "Q4": 8}[pub.quartile]] += share
    rows = []
    for tid, t in sorted(teachers.items(), key=lambda kv: kv[1].full_name):
        rows.append({2: t.full_name, **{c: num(v) for c, v in sums[tid].items()}})
    _data_rows(writer, rows)
    writer.total({2: JAMI, **{c: total_of(rows, c) for c in range(3, 9)}})


# --- 2,2 — maqolalar ro'yxati va iqtiboslar ----------------------------------------
def fill_2_2(writer, data):
    entries = []
    for pub in _publications(data):
        for author in pub.authors.all():
            if data.in_report(author, "2,2", _("статья «%(t)s»") % {"t": pub.article_title[:40]}):
                entries.append((author.full_name, pub))
    entries.sort(key=lambda e: (e[0], -(e[1].publish_year or 0)))
    for i, (name, pub) in enumerate(entries, start=1):
        when = pub.publish_year
        if pub.publish_year and pub.publish_month:
            when = f"{pub.publish_year}.{pub.publish_month:02d}"
        writer.data({1: i, 2: name, 3: pub.journal_name or None, 4: when,
                     5: pub.article_title or None, 6: pub.language or None,
                     7: pub.scopus_url or None, 8: pub.citations_count or None})
        if pub.scopus_url:
            writer.ws.cell(row=writer.row - 1, column=7).hyperlink = pub.scopus_url
    if not entries:
        writer.data({})
    distinct = {pub.id: pub.citations_count for _name, pub in entries}
    writer.total({2: JAMI, 8: sum(distinct.values()) or None})


# --- 2,3 — h-indeks -----------------------------------------------------------------
def fill_2_3(writer, data):
    hindex = {r.teacher_id: r.h_index for r in TeacherHIndex.objects.filter(reporting_period=data.period)}
    rows = _sectioned(writer, data, lambda s: {3: hindex.get(s.teacher_id)})
    writer.total({2: JAMI, 3: total_of(rows, 3)})


# --- 2,4 / 2,5 — patentlar (ulush 1/N) ----------------------------------------------
def _patent_shares(data, sheet, predicate, license_col=False):
    sums = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for patent in Patent.objects.filter(reporting_period=data.period).prefetch_related("authors"):
        if not predicate(patent):
            continue
        share = patent.author_share()
        for author in patent.authors.all():
            if not data.in_report(author, sheet, _("патент «%(t)s»") % {"t": patent.title[:40]}):
                continue
            sums[author.id][0] += share
            if license_col and patent.has_license_agreement:
                sums[author.id][1] += share
    return sums


def fill_2_4(writer, data):
    sums = _patent_shares(data, "2,4", lambda p: p.patent_type in Patent.SHEET_2_4_TYPES, license_col=True)
    rows = _sectioned(writer, data, lambda s: {3: num(sums[s.teacher_id][0]), 4: num(sums[s.teacher_id][1])}
                      if s.teacher_id in sums else {})
    writer.total({2: JAMI, 3: total_of(rows, 3), 4: total_of(rows, 4)})


def fill_2_5(writer, data):
    sums = _patent_shares(data, "2,5", lambda p: p.registered_in_scopus)
    rows = [{2: s.teacher.full_name, 3: num(sums[s.teacher_id][0])}
            for s in data.staff() if s.teacher_id in sums]
    _data_rows(writer, rows)
    writer.total({2: JAMI, 3: total_of(rows, 3)})


# --- 2,6 — jalb etilgan mablag'lar -----------------------------------------------
def fill_2_6(writer, data):
    col = {Funding.SourceType.FOREIGN: 3, Funding.SourceType.STATE_PROGRAM: 4,
           Funding.SourceType.BUSINESS_CONTRACT: 5}
    sums, teachers = defaultdict(lambda: defaultdict(Decimal)), {}
    for f in Funding.objects.filter(reporting_period=data.period).select_related("teacher"):
        if data.in_report(f.teacher, "2,6", _("сумма %(a)s") % {"a": f.amount}):
            sums[f.teacher_id][col[f.source_type]] += f.amount
            teachers[f.teacher_id] = f.teacher
    rows = [{2: t.full_name, **{c: num(v) for c, v in sums[tid].items()}}
            for tid, t in sorted(teachers.items(), key=lambda kv: kv[1].full_name)]
    _data_rows(writer, rows)
    writer.total({2: JAMI, **{c: total_of(rows, c) for c in (3, 4, 5)}})


# --- 2,7 — PhD/DSc himoyalari va darajasiz PO' ------------------------------------
def fill_2_7(writer, data):
    defenses = defaultdict(int)
    for d in PostgradDefense.objects.filter(reporting_period=data.period).select_related("advisor_teacher"):
        if data.in_report(d.advisor_teacher, "2,7", _("защита %(n)s") % {"n": d.defended_full_name}):
            defenses[d.advisor_teacher_id] += 1
    rows = []
    for snap in data.staff():
        count = defenses.get(snap.teacher_id, 0)
        no_degree = snap.academic_degree_id is None
        if count or no_degree:
            rows.append({2: snap.teacher.full_name, 3: count or None, 4: 1 if no_degree else None})
    _data_rows(writer, rows)
    writer.total({2: JAMI, 3: total_of(rows, 3), 4: total_of(rows, 4)})


# --- 3,1 — xalqaro reputatsiya ---------------------------------------------------
def fill_3_1(writer, data):
    col = {ReputationVote.Source.RATING_ORG: 3, ReputationVote.Source.NATIONAL_QA: 4,
           ReputationVote.Source.FOREIGN_PARTNER: 5}
    sums, teachers = defaultdict(lambda: defaultdict(int)), {}
    for v in ReputationVote.objects.filter(reporting_period=data.period).select_related("teacher"):
        if data.in_report(v.teacher, "3,1", _("голосов: %(n)s") % {"n": v.votes_count}):
            sums[v.teacher_id][col[v.source]] += v.votes_count
            teachers[v.teacher_id] = v.teacher
    rows = [{2: t.full_name, **{c: v or None for c, v in sums[tid].items()}}
            for tid, t in sorted(teachers.items(), key=lambda kv: kv[1].full_name)]
    _data_rows(writer, rows)
    writer.total({2: JAMI, **{c: total_of(rows, c) for c in (3, 4, 5)}})


# --- 3,2 — xorijiy talabalar -----------------------------------------------------
def fill_3_2(writer, data):
    col = {Country.Category.HIGH_INCOME: 3, Country.Category.CENTRAL_ASIA: 4, Country.Category.OTHER: 5}
    rows = []
    students = (Student.objects.filter(department=data.period.department, is_active=True,
                                       citizenship_country__is_home_country=False)
                .select_related("citizenship_country").order_by("full_name"))
    for st in students:
        rows.append({2: st.full_name, col[st.citizenship_country.category]: 1})
    _data_rows(writer, rows)
    writer.total({2: JAMI, 3: total_of(rows, 3), 4: total_of(rows, 4), 5: total_of(rows, 5),
                  6: data.period.total_students_count})


# --- 3,3 / 3,5 — talabalar mobilligi va qo'shma dasturlar -------------------------
def _student_program_rows(data, program_type, rank_cols):
    per_student = defaultdict(lambda: defaultdict(int))
    names = {}
    for m in (StudentMobility.objects.filter(reporting_period=data.period, program_type=program_type)
              .select_related("student")):
        per_student[m.student_id][rank_cols[m.partner_rank]] += 1
        names[m.student_id] = m.student.full_name
    return [{2: names[sid], **cols} for sid, cols in sorted(per_student.items(), key=lambda kv: names[kv[0]])]


def fill_3_3(writer, data):
    cols = {Rank.TOP100: 3, Rank.TOP300: 4, Rank.TOP500: 5, Rank.TOP1000: 6, Rank.OTHER: 6}
    rows = _student_program_rows(data, StudentMobility.ProgramType.EXCHANGE, cols)
    _data_rows(writer, rows)
    writer.total({2: JAMI, **{c: total_of(rows, c) for c in (3, 4, 5, 6)},
                  7: data.period.total_students_count})


def fill_3_5(writer, data):
    cols = {Rank.TOP100: 3, Rank.TOP300: 4, Rank.TOP500: 5, Rank.TOP1000: 6, Rank.OTHER: 7}
    rows = _student_program_rows(data, StudentMobility.ProgramType.JOINT_PROGRAM, cols)
    _data_rows(writer, rows)
    writer.total({2: JAMI, **{c: total_of(rows, c) for c in range(3, 8)}})


# --- 3,4 — PO' xalqaro mobilligi --------------------------------------------------
def fill_3_4(writer, data):
    sums, teachers = defaultdict(lambda: [0, 0]), {}
    for m in TeacherMobility.objects.filter(reporting_period=data.period).select_related("teacher"):
        if data.in_report(m.teacher, "3,4", _("мобильность (%(p)s)") % {"p": m.partner_institution_name}):
            sums[m.teacher_id][0 if m.direction == TeacherMobility.Direction.OUTBOUND else 1] += 1
            teachers[m.teacher_id] = m.teacher
    rows = [{2: t.full_name, 3: sums[tid][0] or None, 4: sums[tid][1] or None}
            for tid, t in sorted(teachers.items(), key=lambda kv: kv[1].full_name)]
    _data_rows(writer, rows)
    writer.total({2: JAMI, 3: total_of(rows, 3), 4: total_of(rows, 4)})


# --- 4,1 / 4,2 / 4,3 — bitiruvchilar ----------------------------------------------
def _employment(data):
    return list(
        GraduateEmployment.objects.filter(reporting_period=data.period,
                                          graduate__department=data.period.department)
        .select_related("graduate").order_by("graduate__full_name")
    )


def fill_4_1(writer, data):
    rows = []
    for e in _employment(data):
        employed = e.status != GraduateEmployment.Status.EXEMPT
        rows.append({2: e.graduate.full_name, 3 if employed else 4: 1})
    _data_rows(writer, rows)
    writer.total({2: JAMI, 3: total_of(rows, 3), 4: total_of(rows, 4),
                  5: data.period.total_graduates_count})


def fill_4_2(writer, data):
    col = {3: 3, 6: 4, 12: 5}
    rows = [{2: e.graduate.full_name, col[e.months_to_employment]: 1}
            for e in _employment(data) if e.months_to_employment in col]
    _data_rows(writer, rows)
    writer.total({2: JAMI, 3: total_of(rows, 3), 4: total_of(rows, 4), 5: total_of(rows, 5),
                  6: data.period.total_graduates_count})


def fill_4_3(writer, data):
    d = data.period.period_date
    national = (NationalAvgSalary.objects.filter(year__lt=d.year) |
                NationalAvgSalary.objects.filter(year=d.year, month__lte=d.month)).order_by("-year", "-month").first()
    national_amount = num(national.amount) if national else None
    rows = [{2: e.graduate.full_name, 3: num(e.monthly_income), 4: national_amount}
            for e in _employment(data) if e.monthly_income]
    _data_rows(writer, rows)
    incomes = [Decimal(str(r[3])) for r in rows if r.get(3)]
    writer.total({2: "O‘rtacha:", 3: num(sum(incomes) / len(incomes)) if incomes else None,
                  4: national_amount})


# --- 5 — shtat jadvali ------------------------------------------------------------
def fill_5(writer, data):
    def row(snap):
        t = snap.teacher
        return {3: t.birth_date.year if t.birth_date else None,
                4: snap.position.name if snap.position else None,
                5: num(snap.stavka),
                6: snap.academic_degree.name if snap.academic_degree else None,
                7: snap.academic_title.name if snap.academic_title else None}

    _sectioned(writer, data, row, sections=STAFFING_SECTIONS, always_marker=True)


SHEET_FILLERS = {
    "1,1": fill_1_1, "1,2": fill_1_2, "1,3": fill_1_3, "1,4": fill_1_4,
    "2,1": fill_2_1, "2,2": fill_2_2, "2,3": fill_2_3, "2,4": fill_2_4,
    "2,5": fill_2_5, "2,6": fill_2_6, "2,7": fill_2_7,
    "3,1": fill_3_1, "3,2": fill_3_2, "3,3": fill_3_3, "3,4": fill_3_4, "3,5": fill_3_5,
    "4,1": fill_4_1, "4,2": fill_4_2, "4,3": fill_4_3,
    "5": fill_5,
}
