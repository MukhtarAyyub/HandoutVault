"""
accounts.admin
==============
Registers User with Django's built-in admin site, extending the stock
UserAdmin (which already gives us search, filtering, and a safe
password-change form) with our extra `role` / `student_id` fields.

This IS the "Admin dashboard" for managing student accounts described in
the spec — see materials.views.admin_dashboard for the small custom
statistics page layered on top for the parts (totals, recent activity)
that the built-in admin doesn't show at a glance.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "student_id", "is_active")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name", "student_id")
    fieldsets = BaseUserAdmin.fieldsets + (("Platform role", {"fields": ("role", "student_id")}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Platform role", {"fields": ("role", "student_id")}),)


admin.site.site_header = "HandoutVault Administration"
admin.site.site_title = "HandoutVault Admin"
admin.site.index_title = "Manage the catalog"
