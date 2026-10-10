"""
materials.models
=================
Material is the record students actually came for: an uploaded file plus
the metadata needed to find it again (course, level, semester, session,
topic, week) and to display it usefully (file_type, file_size).

Design notes:

  * file_type / file_size are computed and stored in Material.save()
    rather than read from `file` on every request. Once materials move
    to remote object storage (see README, "Swapping in cloud storage"),
    each `.size` access is a network call — computing once at save time
    keeps every other page read-only against the database.

  * material_upload_path() namespaces files by course and session
    (materials/<code>/<session>/<filename>) purely so the storage
    backend's directory listing stays human-browsable; Django never
    relies on this path for lookups, only the `file` field's stored
    value does.

  * Course/Semester/AcademicSession use on_delete=CASCADE/PROTECT
    deliberately different: deleting a Course should take its Materials
    with it (CASCADE), but deleting a Semester or AcademicSession that
    still has Materials filed under it is almost certainly a mistake —
    PROTECT raises an error instead of silently orphaning files.

Download is a append-only log (one row per download, never updated) —
see materials.views.material_download. It powers both the per-material
`download_count` property and the Admin dashboard's aggregate totals.
"""
import os

from django.conf import settings
from django.db import models
from django.urls import reverse

from academics.models import AcademicSession, Course, Semester

from .validators import validate_material_file


def material_upload_path(instance, filename):
    # e.g. materials/SWE201/2026-2027/Lecture_03.pdf
    session = instance.session.name.replace("/", "-") if instance.session_id else "unassigned"
    course_code = instance.course.code if instance.course_id else "unassigned"
    return f"materials/{course_code}/{session}/{filename}"


class Material(models.Model):
    class Level(models.IntegerChoices):
        L100 = 100, "100 Level"
        L200 = 200, "200 Level"
        L300 = 300, "300 Level"
        L400 = 400, "400 Level"
        L500 = 500, "500 Level"

    title = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="materials")
    level = models.IntegerField(choices=Level.choices)
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT, related_name="materials")
    session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name="materials")
    topic = models.CharField(max_length=200, blank=True)
    week = models.PositiveSmallIntegerField(blank=True, null=True)
    description = models.TextField(blank=True)

    file = models.FileField(upload_to=material_upload_path, validators=[validate_material_file])
    file_type = models.CharField(max_length=10, blank=True, editable=False)
    file_size = models.PositiveIntegerField(blank=True, null=True, editable=False)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_materials",
    )
    upload_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-upload_date"]
        indexes = [
            models.Index(fields=["level"]),
            models.Index(fields=["topic"]),
            models.Index(fields=["file_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.course.code} — {self.title}"

    def save(self, *args, **kwargs):
        if self.file:
            self.file_type = os.path.splitext(self.file.name)[1].lstrip(".").lower()
            try:
                self.file_size = self.file.size
            except (FileNotFoundError, ValueError):
                pass
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("materials:material_detail", args=[self.pk])

    @property
    def is_previewable(self) -> bool:
        return self.file_type == "pdf"

    @property
    def filename(self) -> str:
        """Just the filename, without the materials/<course>/<session>/ prefix."""
        return os.path.basename(self.file.name) if self.file else ""

    @property
    def download_count(self) -> int:
        return self.downloads.count()


class Download(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="downloads")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="downloads"
    )
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-downloaded_at"]

    def __str__(self) -> str:
        return f"{self.student} downloaded {self.material}"
