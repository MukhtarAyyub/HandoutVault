"""
materials.admin
================
Admin-site registration for Material and Download.

In everyday use, Admins upload/edit/delete materials through the
project's own pages (materials.views.material_upload etc.) — those give
students-eye-view previews and the course/level/semester dropdowns tuned
for this one form. This admin registration exists mainly as a safety net
(bulk actions, raw metadata edits, and — via `autocomplete_fields` —
fast course lookup when there are hundreds of them) and to expose
Download as a read-only log for spot-checking.
"""
from django.contrib import admin

from .models import Download, Material


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "level", "semester", "session", "file_type", "upload_date", "uploaded_by")
    list_filter = ("level", "semester", "session", "file_type", "course__department__faculty")
    search_fields = ("title", "topic", "course__code", "course__title")
    readonly_fields = ("file_type", "file_size", "upload_date", "updated_at")
    autocomplete_fields = ["course"]


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):
    list_display = ("material", "student", "downloaded_at")
    list_filter = ("downloaded_at",)
    search_fields = ("material__title", "student__username")
    date_hierarchy = "downloaded_at"
