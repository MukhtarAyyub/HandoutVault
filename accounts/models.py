"""
accounts.models
================
The custom User model shared by both platform roles.

We use ONE Django user model with a `role` field rather than two separate
models (Admin/Student), because:
  * Django's auth system (login, permissions, `request.user`) is built
    around a single AUTH_USER_MODEL — juggling two would mean two login
    systems.
  * Materials, Bookmarks, and Downloads all need a "who did this" foreign
    key; one model gives them one target instead of two nullable FKs.
  * Promoting a student to Admin (or the reverse) is then a one-field
    change instead of a delete-and-recreate.

See accounts.permissions for how the role is enforced in views.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    A single user model for both platform roles.

    Admins get full control of the catalog and materials (and are marked
    as Django staff so they can also use /admin/). Students get read,
    download, and bookmark access only — enforced in views via
    accounts.permissions.admin_required / AdminRequiredMixin, never by
    trusting the client.
    """

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STUDENT = "student", "Student"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    student_id = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        unique=True,
        help_text="Required for students; left blank for Admin accounts.",
    )

    @property
    def is_admin_role(self) -> bool:
        return self.role == self.Role.ADMIN

    def save(self, *args, **kwargs):
        # Keep the Django admin-site flag in sync with our own Admin role,
        # so promoting someone to Admin also gives them /admin/ access.
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.get_full_name() or self.username
