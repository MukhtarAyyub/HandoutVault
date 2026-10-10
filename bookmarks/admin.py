"""
bookmarks.admin
================
Read-mostly admin registration — mainly useful for spot-checking or
manually removing a bookmark on a student's behalf; there's no bulk
"manage bookmarks" workflow in the spec, so nothing fancier is built here.
"""
from django.contrib import admin

from .models import Bookmark


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("student", "material", "created_at")
    search_fields = ("student__username", "material__title")
