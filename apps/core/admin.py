from django.contrib import admin

from .models import University, Faculty, Department


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("short_name", "name")
    search_fields = ("name", "short_name")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "university")
    list_filter = ("university",)
    search_fields = ("name", "short_name")
    autocomplete_fields = ("university",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "faculty")
    list_filter = ("faculty__university", "faculty")
    search_fields = ("name", "short_name")
    autocomplete_fields = ("faculty",)
