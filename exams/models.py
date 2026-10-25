"""
exams.models
============
Exam Preparation content: **Past Questions** and **Summaries**.

Both hang off the SAME academic structure as handouts
(Faculty -> Department -> Course, plus level / semester / session), so a
student finds a course's handouts, past questions and summaries the same
way. They are deliberately separate tables from `materials.Material`:

  * An Admin adds and manages them separately from handouts (own upload
    pages, own admin lists) — "same structure, different way".
  * Each can grow its own fields. A Summary can point at the handout it
    summarises (`Summary.handout`); a Past Question can't.

The shared fields live once, in the abstract `ExamResource`, so the two
models can't drift apart. File rules are NOT re-implemented here: both
reuse `materials.validators.validate_material_file` (extension whitelist,
size cap and real content check), so an exam-prep upload is exactly as
strictly validated as a handout upload.
"""
import os

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from academics.models import AcademicSession, Course, Semester
from materials.models import Material
from materials.validators import validate_material_file


def exam_upload_path(instance, filename):
    """
    exam-prep/<kind>/<course-code>/<session>/<filename>

    Course code and session are slugified so spaces or slashes typed into
    the catalog ("CSE  201", "2026/2027") never end up in storage keys.
    """
    course_part = slugify(instance.course.code) if instance.course_id else "unassigned"
    session_part = slugify(instance.session.name.replace("/", "-")) if instance.session_id else "unassigned"
    return f"exam-prep/{instance.kind_slug}/{course_part}/{session_part}/{filename}"


class ExamResource(models.Model):
    """Fields and behaviour shared by every kind of exam-preparation content."""

    # Set by each concrete subclass. `kind_slug` is the URL segment
    # (/exam-prep/<kind_slug>/...) and part of the storage path.
    kind_slug = ""
    kind_label = ""

    title = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    level = models.IntegerField(choices=Material.Level.choices)
    semester = models.ForeignKey(Semester, on_delete=models.PROTECT)
    session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT)
    description = models.TextField(blank=True)

    file = models.FileField(upload_to=exam_upload_path, validators=[validate_material_file])
    file_type = models.CharField(max_length=10, blank=True, editable=False)
    file_size = models.PositiveIntegerField(blank=True, null=True, editable=False)
    # A plain counter (not a log row per download like Material has): exam
    # content only needs "how popular is this", not "who downloaded it when".
    download_count = models.PositiveIntegerField(default=0, editable=False)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False
    )
    upload_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-upload_date"]

    def __str__(self) -> str:
        return f"{self.course.code} - {self.title}"

    def save(self, *args, **kwargs):
        # Same idea as Material.save(): work out type/size once, at save time.
        if self.file:
            self.file_type = os.path.splitext(self.file.name)[1].lstrip(".").lower()
            try:
                self.file_size = self.file.size
            except (FileNotFoundError, ValueError):
                pass
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("exams:detail", args=[self.kind_slug, self.pk])

    @property
    def is_previewable(self) -> bool:
        return self.file_type == "pdf"

    @property
    def filename(self) -> str:
        return os.path.basename(self.file.name) if self.file else ""


class PastQuestion(ExamResource):
    """A past examination paper for a course, for one session and semester."""

    kind_slug = "past-questions"
    kind_label = "Past question"

    class Meta(ExamResource.Meta):
        verbose_name = "past question"
        verbose_name_plural = "past questions"


class Summary(ExamResource):
    """A revision summary — optionally of one specific handout."""

    kind_slug = "summaries"
    kind_label = "Summary"

    # SET_NULL, not CASCADE: deleting a handout shouldn't silently delete a
    # summary an Admin took the time to write. It just becomes unlinked.
    handout = models.ForeignKey(
        Material,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="summaries",
        help_text="The handout this summarises (optional). Must be from the same course.",
    )

    class Meta(ExamResource.Meta):
        verbose_name = "summary"
        verbose_name_plural = "summaries"
