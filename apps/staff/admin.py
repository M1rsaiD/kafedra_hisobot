from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.utils.text import slugify
from django.utils.translation import gettext as _g, gettext_lazy as _

from .models import Teacher, TeacherPeriodSnapshot

User = get_user_model()


class TeacherPeriodSnapshotInline(admin.TabularInline):
    model = TeacherPeriodSnapshot
    extra = 0
    autocomplete_fields = ("reporting_period", "position", "academic_degree", "academic_title")


def _unique_username(full_name, teacher_id):
    base = slugify(full_name)[:20] or f"teacher{teacher_id}"
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}{suffix}"
    return username


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("full_name", "department", "birth_date", "is_active", "has_login")
    list_filter = ("department", "is_active")
    search_fields = ("full_name",)
    autocomplete_fields = ("department", "user")
    inlines = [TeacherPeriodSnapshotInline]
    actions = ["create_login"]
    PROFILE_FIELDS = (
        "specialty_name", "diploma_series", "diploma_number", "diploma_file",
        "foreign_university_name", "foreign_degree_rank",
        "hire_order_number", "hire_order_date", "hire_order_file",
        "foreign_master_university", "foreign_master_rank", "master_diploma_file",
        "is_foreign_citizen", "citizenship_country",
    )
    fieldsets = (
        (None, {"fields": ("department", "user", "full_name", "birth_date", "is_active")}),
        (_("Дипломы, приказ, гражданство — вносит сам преподаватель в личном кабинете"), {
            "fields": PROFILE_FIELDS,
            "description": _("Эти поля преподаватель заполняет сам через /kabinet/profile/ — "
                             "здесь они показаны для проверки; править их в админке может "
                             "только суперпользователь, чтобы исправить ошибку."),
        }),
    )
    readonly_fields = PROFILE_FIELDS

    def get_readonly_fields(self, request, obj=None):
        # Суперпользователю оставляем возможность исправить ошибку преподавателя,
        # обычным сотрудникам кафедры — только просмотр (ввод идёт через кабинет).
        if request.user.is_superuser:
            return ()
        return self.readonly_fields

    @admin.display(boolean=True, description=_("Есть логин"))
    def has_login(self, obj):
        return obj.user_id is not None

    @admin.action(description=_("Создать логин в личном кабинете для выбранных преподавателей"))
    def create_login(self, request, queryset):
        created = 0
        for teacher in queryset.select_related("user"):
            if teacher.user_id:
                self.message_user(
                    request, _g("%(name)s: логин уже есть (%(login)s) — пропущено.")
                    % {"name": teacher.full_name, "login": teacher.user.username},
                    level=messages.WARNING,
                )
                continue
            username = _unique_username(teacher.full_name, teacher.id)
            password = get_random_string(10)
            user = User.objects.create_user(username=username, password=password, is_staff=False)
            teacher.user = user
            teacher.save(update_fields=["user"])
            created += 1
            self.message_user(
                request,
                _g("%(name)s: логин «%(login)s», пароль «%(password)s» (сообщите преподавателю "
                   "лично — пароль больше нигде не сохранён).")
                % {"name": teacher.full_name, "login": username, "password": password},
                level=messages.SUCCESS,
            )
        if created == 0:
            self.message_user(request, _g("Новых логинов не создано."), level=messages.INFO)


@admin.register(TeacherPeriodSnapshot)
class TeacherPeriodSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "teacher", "reporting_period", "employment_type", "position",
        "stavka", "academic_degree", "academic_title",
    )
    list_filter = ("reporting_period", "employment_type", "academic_degree")
    search_fields = ("teacher__full_name",)
    autocomplete_fields = ("teacher", "reporting_period", "position", "academic_degree", "academic_title")
