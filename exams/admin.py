"""
exams.admin
===========
Safety-net registration in Django's admin (bulk actions, raw edits). Day to
day, Admins add past questions and summaries through the site's own pages
(/exam-prep/<kind>/add/); these lists are the "see everything at once" view.
"""
from django.contrib import admin

from .models import PastQuestion, Summary


class _ExamResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "level", "semester", "session", "file_type", "download_count", "upload_date")
    list_filter = ("level", "semester", "session", "course__department__faculty")
    search_fields = ("title", "description", "course__code", "course__title")
    readonly_fields = ("uploaded_by", "file_type", "file_size", "download_count", "upload_date", "updated_at")
    autocomplete_fields = ["course"]

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PastQuestion)
class PastQuestionAdmin(_ExamResourceAdmin):
    pass


@admin.register(Summary)
class SummaryAdmin(_ExamResourceAdmin):
    list_display = _ExamResourceAdmin.list_display + ("handout",)
    autocomplete_fields = ["course", "handout"]
