"""
Конфигурация самообслуживания преподавателя: какие разделы формы он ведёт
сам (список, добавление, редактирование, удаление только своих записей),
какими полями и что показывать в списке.

Два вида владения записью:
- teacher_field — запись принадлежит одному преподавателю (FK);
- authors=True  — общая запись нескольких авторов кафедры (M2M, статья,
  патент): её видят и правят все отмеченные соавторы, а в своды каждому
  засчитывается доля 1/N (N — общее число авторов, поле authors_total).

Чтобы добавить преподавателям ещё один раздел, достаточно дописать сюда
одну запись — отдельная страница/форма не нужна: generic-views в views.py
работают с любым слагом из REGISTRY.
"""

from django.utils.translation import gettext_lazy as _

from apps.reports.models import (
    Funding, Patent, PostgradDefense, Publication, ReputationVote, TeacherHIndex, TeacherMobility,
)

REGISTRY = {
    "publications": {
        "model": Publication,
        "authors": True,
        "creator_field": "teacher",
        "sheet": "2,1 – 2,2",
        "title": _("Статьи (Scopus)"),
        "fields": [
            "reporting_period", "article_title", "journal_name", "publish_year", "publish_month",
            "language", "scopus_url", "quartile", "citation_tier", "citations_count",
            "authors_total", "article_file",
        ],
        "list_columns": ["article_title", "publish_year", "quartile", "citations_count"],
        "file_field": "article_file",
    },
    "patents": {
        "model": Patent,
        "authors": True,
        "sheet": "2,4 – 2,5",
        "title": _("Патенты и свидетельства (DGU)"),
        "fields": [
            "reporting_period", "title", "patent_type", "number", "issue_date",
            "authors_total", "registered_in_scopus", "has_license_agreement", "document_file",
        ],
        "list_columns": ["title", "patent_type", "number"],
        "file_field": "document_file",
    },
    "hindex": {
        "model": TeacherHIndex,
        "teacher_field": "teacher",
        "sheet": "2,3",
        "title": _("Индекс Хирша (h-index)"),
        "fields": ["reporting_period", "h_index", "scopus_profile_url", "document_file"],
        "list_columns": ["h_index", "scopus_profile_url"],
        "file_field": "document_file",
    },
    "fundings": {
        "model": Funding,
        "teacher_field": "teacher",
        "sheet": "2,6",
        "title": _("Привлечённые средства"),
        "fields": ["reporting_period", "source_type", "amount", "contract_info", "document_file"],
        "list_columns": ["source_type", "amount", "contract_info"],
        "file_field": "document_file",
    },
    "defenses": {
        "model": PostgradDefense,
        "teacher_field": "advisor_teacher",
        "sheet": "2,7",
        "title": _("Защиты под моим руководством"),
        "fields": ["reporting_period", "degree_type", "defended_full_name", "defense_date", "document_file"],
        "list_columns": ["degree_type", "defended_full_name", "defense_date"],
        "file_field": "document_file",
    },
    "reputation": {
        "model": ReputationVote,
        "teacher_field": "teacher",
        "sheet": "3,1",
        "title": _("Международная репутация (голоса)"),
        "fields": ["reporting_period", "source", "votes_count", "note", "document_file"],
        "list_columns": ["source", "votes_count", "note"],
        "file_field": "document_file",
    },
    "mobility": {
        "model": TeacherMobility,
        "teacher_field": "teacher",
        "sheet": "3,4",
        "title": _("Международная мобильность"),
        "fields": [
            "reporting_period", "direction", "partner_institution_name", "start_date", "end_date",
            "order_info", "document_file",
        ],
        "list_columns": ["direction", "partner_institution_name", "start_date"],
        "file_field": "document_file",
    },
}


def teacher_queryset(cfg, teacher):
    model = cfg["model"]
    if cfg.get("authors"):
        return model.objects.filter(authors=teacher).distinct()
    return model.objects.filter(**{cfg["teacher_field"]: teacher})
