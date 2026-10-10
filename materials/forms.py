"""
materials.forms
================
One form, used for both create and edit (materials.views.material_upload
and material_edit pass it different `instance=` values but the same
class and template).

File validation (extension whitelist + size limit) is NOT implemented
here — it's attached directly to the model field as a validator
(`materials.models.Material.file`, using `materials.validators.
validate_material_file`). Django's ModelForm runs model-field validators
automatically during `is_valid()`, so it applies equally whether a
Material is created through this form, the Django admin, or a script —
there's exactly one place file rules are defined.
"""
from django import forms

from academics.models import Course

from .models import Material


class MaterialUploadForm(forms.ModelForm):
    """
    Used for both upload and edit — Admin-only (enforced with
    @admin_required in the view, not here; a form has no concept of
    "who's allowed to submit me").
    """

    class Meta:
        model = Material
        fields = [
            "title",
            "course",
            "level",
            "semester",
            "session",
            "topic",
            "week",
            "description",
            "file",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["course"].queryset = Course.objects.select_related(
            "department", "department__faculty"
        ).order_by("department__faculty__name", "department__name", "code")
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            widget_type = field.widget.__class__.__name__
            if widget_type in ("CheckboxInput",):
                field.widget.attrs["class"] = (existing + " form-check-input").strip()
            elif widget_type in ("Select", "SelectMultiple"):
                field.widget.attrs["class"] = (existing + " form-select").strip()
            else:
                field.widget.attrs["class"] = (existing + " form-control").strip()
