"""
academics.admin
================
Admin-site registration for the catalog hierarchy. This is where an
Admin actually builds out the academic structure — there's no public
"add a Faculty" page in the app itself (see the spec's own scoping in
section 4: only Admin/Student roles, Admin has "complete control").

`prepopulated_fields` auto-fills each slug from its name in the browser
(via JS in the admin), matching the slugify() fallback already in
Faculty.save() / Department.save() for anything created outside the
admin (e.g. a data migration or the Django shell).
"""
from django.contrib import admin

from .models import AcademicSession, Course, Department, Faculty, Semester


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "faculty", "slug")
    list_filter = ("faculty",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "department")
    list_filter = ("department__faculty", "department")
    search_fields = ("code", "title")


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ("name",)
