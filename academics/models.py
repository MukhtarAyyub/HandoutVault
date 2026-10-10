"""
academics.models
=================
The academic hierarchy materials are filed under:

    Faculty -> Department -> Course -> (AcademicSession, Semester, Level)

Faculty/Department/Course are separate tables because each is a distinct,
independently-manageable record with its own name and (for the first two)
URL slug. AcademicSession and Semester are also separate tables — rather
than free-text fields on Material — so the filter dropdowns in the
materials list always reflect a clean, finite set of real values instead
of however many ways someone typed "2026/2027" by hand.

Level is deliberately NOT its own table: it's a fixed, small set of
numeric choices (100-500) that never needs independent metadata, so it
lives directly on Material as an IntegerChoices field (see
materials.models.Material.Level) instead of adding a fifth join.
"""
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Faculty(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Faculties"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("academics:department_list", args=[self.slug])


class Department(models.Model):
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("faculty", "slug")

    def __str__(self) -> str:
        return f"{self.name} — {self.faculty.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("academics:course_list", args=[self.faculty.slug, self.slug])


class Course(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="courses")
    code = models.CharField(max_length=20, db_index=True, help_text="e.g. SWE201")
    title = models.CharField(max_length=200, db_index=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("department", "code")

    def __str__(self) -> str:
        return f"{self.code} — {self.title}"


class AcademicSession(models.Model):
    name = models.CharField(max_length=20, unique=True, help_text="e.g. 2026/2027")

    class Meta:
        ordering = ["-name"]

    def __str__(self) -> str:
        return self.name


class Semester(models.Model):
    class Term(models.TextChoices):
        FIRST = "first", "First Semester"
        SECOND = "second", "Second Semester"

    name = models.CharField(max_length=10, choices=Term.choices, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.get_name_display()
