"""
bookmarks.models
=================
A student's saved-for-later materials — deliberately its own small app
rather than a field or M2M tucked onto User or Material, because it has
its own lifecycle (created/deleted independently of either side) and its
own admin-safety-net registration. `unique_together` is what makes
"toggle" semantics in bookmarks.views.toggle_bookmark safe: a second
bookmark attempt for the same (student, material) pair can't silently
create a duplicate row.
"""
from django.conf import settings
from django.db import models

from materials.models import Material


class Bookmark(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="bookmarked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "material")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student} → {self.material}"
