"""
Конкретные функции заполнения листов. Каждая функция получает лист openpyxl
(уже открытый из шаблона) и ReportingPeriod, и пишет значения в те же ячейки,
которые в оригинальном файле министерства заполнены вручную.

Ряды/колонки ниже — не догадка, а результат разбора реального файла
(kafedra_hisobot_template.xlsx), см. комментарии у каждой функции.

Ограничение, которое стоит знать: количество строк под каждую секцию в
шаблоне фиксировано (столько, сколько было в исходном файле на момент
выгрузки). Если сотрудников станет больше, чем строк-заготовок — вызовите
ws.insert_rows(...) перед записью (см. TODO в fill_staffing_sheet) либо
расширьте шаблон вручную на одну строку с той же заливкой/границами.
"""

from collections import defaultdict
from decimal import Decimal

from apps.staff.models import TeacherPeriodSnapshot
from apps.reports.models import (
    TeacherHIndex, Publication, Patent, PatentAuthor, Funding,
    PostgradDefense, TeacherMobility,
)


# ---------------------------------------------------------------------------
# Лист "5" — штатная ведомость (5-jadval)
# Колонки: A=T/r, B=Ф.И.Ш., C=год рождения, D=должность, E=ставка,
#          F=учёная степень, G=учёное звание
# Секции (по employment_type), с фиксированным числом строк-заготовок,
# как в исходном файле:
#   asosiy_shtat      -> строки 7..20  (14 строк)
#   ichki_orindosh    -> строка  22    (1 строка)
#   tashqi_orindosh   -> строки 24..26 (3 строки)
#   soatbay           -> строки 28..30 (3 строки)
# ---------------------------------------------------------------------------
_STAFFING_SECTIONS = [
    ("asosiy", 7, 20),
    ("ichki_orindosh", 22, 22),
    ("tashqi_orindosh", 24, 26),
    ("soatbay", 28, 30),
]


def fill_staffing_sheet(ws, period):
    for code, start_row, end_row in _STAFFING_SECTIONS:
        snapshots = list(
            TeacherPeriodSnapshot.objects.filter(
                reporting_period=period, employment_type__code=code,
            )
            .select_related("teacher", "position", "academic_degree", "academic_title")
            .order_by("teacher__full_name")
        )

        capacity = end_row - start_row + 1
        if len(snapshots) > capacity:
            # TODO: ws.insert_rows(end_row + 1, amount=len(snapshots) - capacity)
            # и скопировать стиль последней строки шаблона на новые строки.
            snapshots = snapshots[:capacity]

        row = start_row
        for i, snap in enumerate(snapshots, start=1):
            ws.cell(row=row, column=1).value = i
            ws.cell(row=row, column=2).value = snap.teacher.full_name
            ws.cell(row=row, column=3).value = (
                snap.teacher.birth_date.year if snap.teacher.birth_date else None
            )
            ws.cell(row=row, column=4).value = snap.position.name if snap.position else None
            ws.cell(row=row, column=5).value = float(snap.stavka)
            ws.cell(row=row, column=6).value = snap.academic_degree.name if snap.academic_degree else None
            ws.cell(row=row, column=7).value = snap.academic_title.name if snap.academic_title else None
            row += 1

        # очищаем неиспользованные строки-заготовки, если людей меньше, чем в шаблоне
        for empty_row in range(row, end_row + 1):
            for col in range(1, 8):
                ws.cell(row=empty_row, column=col).value = None


# ---------------------------------------------------------------------------
# Лист "1,1" — доля ППС с учёной степенью/званием, полученной за рубежом
# Колонки: A=T/r, B=Ф.И.Ш., C=назв. зарубежного ОТМ,
#          D,E = серия/номер (Академик), F,G = серия/номер (DSc/профессор),
#          H,I = серия/номер (PhD/доцент), J=специальность, K=приказ о приёме
# Секции: строки 4..17 — asosiy+ichki_orindosh основной штат (14 строк),
#         строка 18 — маркер "Ichki o'rindosh", строка 19 — 1 строка.
# ---------------------------------------------------------------------------
_DEGREE_COLUMN_BY_CODE = {
    "akademik": (4, 5),
    "dsc": (6, 7),
    "fan_doktori": (6, 7),
    "phd": (8, 9),
    "fan_nomzodi": (8, 9),
}


def _write_degree_share_row(ws, row, snap):
    teacher = snap.teacher

    # Важно: сначала очищаем ВСЕ управляемые колонки строки (2..11). Шаблон —
    # это настоящий файл с реальными данными, и если этого не сделать, при
    # изменении порядка/состава списка в ячейках D..K останутся значения от
    # ДРУГОГО преподавателя, который раньше стоял в этой строке в шаблоне.
    for col in range(2, 12):
        ws.cell(row=row, column=col).value = None

    ws.cell(row=row, column=2).value = teacher.full_name
    ws.cell(row=row, column=3).value = teacher.foreign_university_name or None

    cols = _DEGREE_COLUMN_BY_CODE.get(
        snap.academic_degree.code if snap.academic_degree else None
    )
    if cols and teacher.diploma_series:
        ws.cell(row=row, column=cols[0]).value = teacher.diploma_series
        ws.cell(row=row, column=cols[1]).value = teacher.diploma_number

    ws.cell(row=row, column=10).value = teacher.specialty_name or None
    if teacher.hire_order_number:
        order = teacher.hire_order_number
        if teacher.hire_order_date:
            order = f"{order}, {teacher.hire_order_date:%d.%m.%Y}"
        ws.cell(row=row, column=11).value = order


def fill_academic_degree_share_sheet(ws, period):
    main = list(
        TeacherPeriodSnapshot.objects.filter(
            reporting_period=period, employment_type__code="asosiy",
        )
        .select_related("teacher", "academic_degree")
        .order_by("teacher__full_name")
    )
    row = 4
    for i, snap in enumerate(main[: 17 - 4 + 1], start=1):
        ws.cell(row=row, column=1).value = i
        _write_degree_share_row(ws, row, snap)
        row += 1
    for empty_row in range(row, 18):
        for col in range(1, 12):
            ws.cell(row=empty_row, column=col).value = None

    ichki = list(
        TeacherPeriodSnapshot.objects.filter(
            reporting_period=period, employment_type__code="ichki_orindosh",
        )
        .select_related("teacher", "academic_degree")
        .order_by("teacher__full_name")
    )
    row = 19
    for i, snap in enumerate(ichki[:1], start=1):
        ws.cell(row=row, column=1).value = i
        _write_degree_share_row(ws, row, snap)
        row += 1


# ---------------------------------------------------------------------------
# Лист "2,3" — суммарный h-индекс ППС (простой пример: одна колонка-значение)
# Колонки: A=T/r, B=Ф.И.Ш., C=h-индекс. Основной штат: строки 4..17.
# ---------------------------------------------------------------------------
def fill_hindex_sheet(ws, period):
    snapshots = list(
        TeacherPeriodSnapshot.objects.filter(
            reporting_period=period, employment_type__code="asosiy",
        )
        .select_related("teacher")
        .order_by("teacher__full_name")
    )
    hindex_by_teacher = {
        rec.teacher_id: rec.h_index
        for rec in TeacherHIndex.objects.filter(reporting_period=period)
    }
    row = 4
    for i, snap in enumerate(snapshots[:14], start=1):
        ws.cell(row=row, column=1).value = i
        ws.cell(row=row, column=2).value = snap.teacher.full_name
        ws.cell(row=row, column=3).value = hindex_by_teacher.get(snap.teacher_id)
        row += 1


def _share(pubs_qs):
    """1/N-доля публикации на соавтора-сотрудника кафедры (см. Publication.
    department_co_authors_count) — так в исходной методике получаются
    дробные значения вроде 0.33/0.5/0.66 в своде по квартилям."""
    total = Decimal("0")
    for pub in pubs_qs:
        total += Decimal(1) / Decimal(pub.department_co_authors_count or 1)
    if not total:
        return None
    return float(round(total, 2))


def _write_sparse_rows(ws, start_row, end_row, entries, value_columns):
    """Общий помощник для «разреженных» листов (2,4 / 2,6 / 3,4 и т.п.),
    где в шаблоне не 14 строк на весь штат, а несколько строк под тех, у
    кого вообще есть что показать. entries — [(имя, (знач1, знач2, ...)), ...].
    """
    capacity = end_row - start_row + 1
    row = start_row
    for i, (name, values) in enumerate(entries[:capacity], start=1):
        ws.cell(row=row, column=1).value = i
        ws.cell(row=row, column=2).value = name
        for col, value in zip(value_columns, values):
            ws.cell(row=row, column=col).value = value
        row += 1
    for empty_row in range(row, end_row + 1):
        for col in [1, 2] + list(value_columns):
            ws.cell(row=empty_row, column=col).value = None


# ---------------------------------------------------------------------------
# Лист "2,1" — свод публикаций по квартилям/топам цитируемости.
# Колонки: A=T/r,B=Ф.И.Ш.,C=Top1%,D=Top10%,E=Q1,F=Q2,G=Q3,H=Q4 (дробные доли).
# Секции: асосий 3..16 (14), маркер "Ichki oʻrindoshlar" в строке 17 (не
# трогаем), ички 18 (1). Итоговая строка 19 — формула Excel (=SUM(...)) —
# её не трогаем, пересчитается сама при открытии файла.
# ---------------------------------------------------------------------------
def fill_publications_quartile_sheet(ws, period):
    for code, start, end in [("asosiy", 3, 16), ("ichki_orindosh", 18, 18)]:
        snaps = list(
            TeacherPeriodSnapshot.objects.filter(reporting_period=period, employment_type__code=code)
            .select_related("teacher").order_by("teacher__full_name")
        )[: end - start + 1]
        entries = []
        for snap in snaps:
            pubs = Publication.objects.filter(teacher=snap.teacher, reporting_period=period)
            entries.append((snap.teacher.full_name, (
                _share(pubs.filter(citation_tier="top1")),
                _share(pubs.filter(citation_tier="top10")),
                _share(pubs.filter(quartile="Q1")),
                _share(pubs.filter(quartile="Q2")),
                _share(pubs.filter(quartile="Q3")),
                _share(pubs.filter(quartile="Q4")),
            )))
        _write_sparse_rows(ws, start, end, entries, value_columns=[3, 4, 5, 6, 7, 8])


# ---------------------------------------------------------------------------
# Лист "2,4" — патенты/объекты интеллектуальной собственности.
# Колонки: A=T/r,B=Ф.И.Ш.,C=число патентов,D=из них с лицензионным договором.
# Разреженный список (не весь штат) — только те, у кого есть патенты. Строки 3..5.
# ---------------------------------------------------------------------------
def fill_patents_share_sheet(ws, period):
    stats = defaultdict(lambda: [0, 0])
    for pa in PatentAuthor.objects.filter(patent__reporting_period=period).select_related("patent", "teacher"):
        stats[pa.teacher][0] += 1
        if pa.patent.has_license_agreement:
            stats[pa.teacher][1] += 1
    entries = sorted(
        ((t.full_name, tuple(v)) for t, v in stats.items()),
        key=lambda x: x[0],
    )
    _write_sparse_rows(ws, 3, 5, entries, value_columns=[3, 4])


# ---------------------------------------------------------------------------
# Лист "2,6" — привлечённые средства.
# Колонки: A=T/r,B=Ф.И.Ш.,C=зарубежные/международные,D=госпрограммы,E=хоздоговоры.
# Разреженный список. Строки 3..6.
# ---------------------------------------------------------------------------
def fill_funding_sheet(ws, period):
    stats = defaultdict(lambda: [Decimal("0"), Decimal("0"), Decimal("0")])
    idx = {"foreign_international": 0, "state_program": 1, "business_contract": 2}
    for f in Funding.objects.filter(reporting_period=period).select_related("teacher"):
        stats[f.teacher][idx[f.source_type]] += f.amount
    entries = sorted(
        ((t.full_name, tuple(float(v) if v else None for v in vals)) for t, vals in stats.items()),
        key=lambda x: x[0],
    )
    _write_sparse_rows(ws, 3, 6, entries, value_columns=[3, 4, 5])


# ---------------------------------------------------------------------------
# Лист "2,7" — эффективность подготовки кадров высшей квалификации.
# Колонки: A=T/r,B=Ф.И.Ш.,C=число защит под руководством,D=флаг "нет степени".
# Строка попадает в отчёт, если хотя бы одно из двух условий верно.
# Секции: асосий 3..7 (5), маркер строка 8 (не трогаем), ички 9 (1).
# ---------------------------------------------------------------------------
def fill_postgrad_efficiency_sheet(ws, period):
    defense_counts = defaultdict(int)
    for d in PostgradDefense.objects.filter(reporting_period=period):
        defense_counts[d.advisor_teacher_id] += 1

    for code, start, end in [("asosiy", 3, 7), ("ichki_orindosh", 9, 9)]:
        snaps = list(
            TeacherPeriodSnapshot.objects.filter(reporting_period=period, employment_type__code=code)
            .select_related("teacher", "academic_degree").order_by("teacher__full_name")
        )
        entries = []
        for snap in snaps:
            defenses = defense_counts.get(snap.teacher_id, 0)
            no_degree = snap.academic_degree_id is None
            if defenses or no_degree:
                entries.append((snap.teacher.full_name, (
                    defenses or None,
                    1 if no_degree else None,
                )))
        _write_sparse_rows(ws, start, end, entries, value_columns=[3, 4])


# ---------------------------------------------------------------------------
# Лист "3,4" — международная мобильность ППС.
# Колонки: A=T/r,B=Ф.И.Ш.,C=outbound,D=inbound. Разреженный список. Строки 3..5.
# ---------------------------------------------------------------------------
def fill_teacher_mobility_sheet(ws, period):
    stats = defaultdict(lambda: [0, 0])
    for m in TeacherMobility.objects.filter(reporting_period=period).select_related("teacher"):
        stats[m.teacher][0 if m.direction == "outbound" else 1] += 1
    entries = sorted(
        ((t.full_name, tuple(v or None for v in vals)) for t, vals in stats.items()),
        key=lambda x: x[0],
    )
    _write_sparse_rows(ws, 3, 5, entries, value_columns=[3, 4])


SHEET_FILLERS = {
    "5": fill_staffing_sheet,
    "1,1": fill_academic_degree_share_sheet,
    "2,1": fill_publications_quartile_sheet,
    "2,3": fill_hindex_sheet,
    "2,4": fill_patents_share_sheet,
    "2,6": fill_funding_sheet,
    "2,7": fill_postgrad_efficiency_sheet,
    "3,4": fill_teacher_mobility_sheet,
}
