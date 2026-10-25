"""
exams.forms
===========
One ModelForm per kind, used for both "add" and "edit" (Admin only — that is
enforced in the views with @admin_required; a form can't know who is asking).

File validation isn't repeated here: it's a validator on the model field
(see exams.models), so it applies whether the file arrives through these
forms, the Django admin or a script.
"""
from django import forms

from academics.models import Course
from materials.models import Material

from .models import PastQuestion, Summary


class _ExamResourceFormBase(forms.ModelForm):
    """Shared widgets + the course dropdown ordering. Not used directly."""

    class Meta:
        widgets = {"description": forms.Textarea(attrs={"rows": 4}), "file": forms.FileInput}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Group-friendly ordering: faculty, then department, then course code.
        self.fields["course"].queryset = Course.objects.select_related(
            "department", "department__faculty"
        ).order_by("department__faculty__name", "department__name", "code")


class PastQuestionForm(_ExamResourceFormBase):
    class Meta(_ExamResourceFormBase.Meta):
        model = PastQuestion
        fields = ["title", "course", "level", "semester", "session", "description", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["session"].help_text = "The session the exam was written in."


class SummaryForm(_ExamResourceFormBase):
    class Meta(_ExamResourceFormBase.Meta):
        model = Summary
        fields = ["title", "course", "handout", "level", "semester", "session", "description", "file"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["handout"].label = "Related handout"
        self.fields["handout"].queryset = Material.objects.select_related("course").order_by(
            "course__code", "title"
        )
        self.fields["handout"].label_from_instance = lambda m: f"{m.course.code} - {m.title}"

    def clean(self):
        """A summary's handout must belong to the same course the summary is filed under."""
        cleaned = super().clean()
        handout, course = cleaned.get("handout"), cleaned.get("course")
        if handout and course and handout.course_id != course.id:
            self.add_error(
                "handout",
                f"That handout belongs to {handout.course.code}, not {course.code}. "
                "Pick a handout from the same course.",
            )
        return cleaned
