import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Department, Faculty, University
from apps.exporter.importer import Importer, clear_period_data
from apps.workflow.models import ReportingPeriod


class Command(BaseCommand):
    help = (
        "Загрузить в БД уже заполненный вручную файл формы «Umumiy kafedra reytingi» (2026): "
        "преподаватели, штатная ведомость, дипломы, статьи, h-индекс, средства, мобильность."
    )

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path")
        parser.add_argument("--department", required=True,
                            help="Название кафедры, напр. «Amaliy matematika va informatika kafedrasi»")
        parser.add_argument("--period", required=True, help="Метка периода, напр. 2026-iyun")
        parser.add_argument("--date", required=True, help="Дата отчёта (holatiga), ГГГГ-ММ-ДД")
        parser.add_argument("--faculty", default="", help="Факультет (если кафедры ещё нет в БД)")
        parser.add_argument("--university", default="", help="Университет (если кафедры ещё нет в БД)")
        parser.add_argument("--replace", action="store_true",
                            help="Удалить уже внесённые факты этого периода перед импортом.")

    def handle(self, *args, **opts):
        try:
            period_date = datetime.date.fromisoformat(opts["date"])
        except ValueError as exc:
            raise CommandError("--date должна быть в формате ГГГГ-ММ-ДД") from exc

        department = Department.objects.filter(name=opts["department"]).first()
        if department is None:
            if not (opts["faculty"] and opts["university"]):
                raise CommandError("Кафедра не найдена. Укажите --faculty и --university, чтобы создать её.")
            uni, _ = University.objects.get_or_create(name=opts["university"])
            fac, _ = Faculty.objects.get_or_create(university=uni, name=opts["faculty"])
            department = Department.objects.create(faculty=fac, name=opts["department"])
            self.stdout.write(f"Создана кафедра: {department.name}")

        period, created = ReportingPeriod.objects.get_or_create(
            department=department, period_label=opts["period"], defaults={"period_date": period_date},
        )
        if not created and period.teacher_snapshots.exists():
            if not opts["replace"]:
                raise CommandError("В этом периоде уже есть данные. Повторите с --replace, чтобы перезаписать.")
            clear_period_data(period)

        stats, unmatched = Importer(opts["xlsx_path"], period).run()
        self.stdout.write(self.style.SUCCESS(f"Импортировано в «{period}» (id кафедры {department.id}):"))
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value}")
        for line in unmatched:
            self.stdout.write(self.style.WARNING(f"  ! {line}"))
