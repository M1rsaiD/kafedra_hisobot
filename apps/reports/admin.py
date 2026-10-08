from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Publication, PublicationAuthor, TeacherHIndex, Patent, PatentAuthor, Funding,
    PostgradDefense, ReputationVote, TeacherMobility, StudentMobility,
    GraduateEmployment, NationalAvgSalary, IndicatorValue,
)


@admin.display(boolean=True, description=_("Файл"))
def has_file(obj):
    for name in ("article_file", "document_file"):
        if hasattr(obj, name):
            return bool(getattr(obj, name))
    return False


class PublicationAuthorInline(admin.TabularInline):
    model = PublicationAuthor
    extra = 1
    autocomplete_fields = ("teacher",)


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ("article_title", "reporting_period", "authors_list", "authors_total", "quartile",
                    "citation_tier", "citations_count", "publish_year", has_file)
    list_filter = ("reporting_period", "quartile", "citation_tier", "publish_year")
    search_fields = ("authors__full_name", "article_title", "journal_name")
    autocomplete_fields = ("teacher", "reporting_period")
    inlines = [PublicationAuthorInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("authors")

    @admin.display(description=_("Авторы кафедры"))
    def authors_list(self, obj):
        return ", ".join(a.full_name for a in obj.authors.all())


@admin.register(TeacherHIndex)
class TeacherHIndexAdmin(admin.ModelAdmin):
    list_display = ("teacher", "reporting_period", "h_index", has_file)
    list_filter = ("reporting_period",)
    search_fields = ("teacher__full_name",)
    autocomplete_fields = ("teacher", "reporting_period")


class PatentAuthorInline(admin.TabularInline):
    model = PatentAuthor
    extra = 1
    autocomplete_fields = ("teacher",)


@admin.register(Patent)
class PatentAdmin(admin.ModelAdmin):
    list_display = ("title", "reporting_period", "patent_type", "number", "authors_total",
                    "registered_in_scopus", "has_license_agreement", has_file)
    list_filter = ("reporting_period", "patent_type", "registered_in_scopus")
    search_fields = ("title", "number", "authors__full_name")
    autocomplete_fields = ("reporting_period",)
    inlines = [PatentAuthorInline]


@admin.register(Funding)
class FundingAdmin(admin.ModelAdmin):
    list_display = ("teacher", "reporting_period", "source_type", "amount", "contract_info", has_file)
    list_filter = ("reporting_period", "source_type")
    search_fields = ("teacher__full_name", "contract_info")
    autocomplete_fields = ("teacher", "reporting_period")


@admin.register(PostgradDefense)
class PostgradDefenseAdmin(admin.ModelAdmin):
    list_display = ("advisor_teacher", "reporting_period", "degree_type", "defended_full_name", has_file)
    list_filter = ("reporting_period", "degree_type")
    search_fields = ("advisor_teacher__full_name", "defended_full_name")
    autocomplete_fields = ("advisor_teacher", "reporting_period")


@admin.register(ReputationVote)
class ReputationVoteAdmin(admin.ModelAdmin):
    list_display = ("teacher", "reporting_period", "source", "votes_count", has_file)
    list_filter = ("reporting_period", "source")
    search_fields = ("teacher__full_name",)
    autocomplete_fields = ("teacher", "reporting_period")


@admin.register(TeacherMobility)
class TeacherMobilityAdmin(admin.ModelAdmin):
    list_display = ("teacher", "reporting_period", "direction", "partner_institution_name", "order_info", has_file)
    list_filter = ("reporting_period", "direction")
    search_fields = ("teacher__full_name", "partner_institution_name")
    autocomplete_fields = ("teacher", "reporting_period")


@admin.register(StudentMobility)
class StudentMobilityAdmin(admin.ModelAdmin):
    list_display = ("student", "reporting_period", "program_type", "partner_rank",
                    "partner_institution_name", has_file)
    list_filter = ("reporting_period", "program_type", "partner_rank")
    search_fields = ("student__full_name", "partner_institution_name")
    autocomplete_fields = ("student", "reporting_period")


@admin.register(GraduateEmployment)
class GraduateEmploymentAdmin(admin.ModelAdmin):
    list_display = ("graduate", "reporting_period", "status", "months_to_employment", "monthly_income", has_file)
    list_filter = ("reporting_period", "status")
    search_fields = ("graduate__full_name",)
    autocomplete_fields = ("graduate", "reporting_period")


@admin.register(NationalAvgSalary)
class NationalAvgSalaryAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "amount")
    ordering = ("-year", "-month")


@admin.register(IndicatorValue)
class IndicatorValueAdmin(admin.ModelAdmin):
    list_display = ("indicator_code", "subject_type", "subject_id", "reporting_period", "value_numeric", "value_text")
    list_filter = ("reporting_period", "subject_type")
    search_fields = ("indicator_code",)
    autocomplete_fields = ("reporting_period",)
