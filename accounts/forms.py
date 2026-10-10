from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


def _apply_form_control_classes(form):
    """Add Bootstrap classes to every field's widget (no template-side work needed)."""
    for field in form.fields.values():
        widget_type = field.widget.__class__.__name__
        if widget_type in ("Select", "SelectMultiple"):
            field.widget.attrs["class"] = "form-select"
        elif widget_type == "CheckboxInput":
            field.widget.attrs["class"] = "form-check-input"
        else:
            field.widget.attrs["class"] = "form-control"


class StyledAuthenticationForm(AuthenticationForm):
    """Django's built-in login form, restyled to match the rest of the site."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_control_classes(self)


class StudentRegistrationForm(UserCreationForm):
    """
    Public registration form. Always creates a Student account — Admin
    accounts are created separately via `manage.py createsuperuser` or
    promoted in /admin/, never through this public form.
    """

    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    student_id = forms.CharField(
        max_length=30,
        required=True,
        label="Student ID",
        help_text="Your official university-issued student ID.",
    )
    # Bot protection (see SECURITY.md, "Add bot protection"). Real users
    # never see or fill this in — it's positioned off-screen by the
    # ".hp-field-wrap" class in register.html and skipped in the tab
    # order — so anything that DOES fill it in is almost certainly an
    # automated submission, not a person. It's declared here as a plain
    # form field (not in Meta.fields, so it's never written to User) and
    # rejected in clean_website below.
    website = forms.CharField(
        required=False,
        label="Leave this field blank",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "student_id",
            "email",
            "username",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_control_classes(self)

    def clean_website(self):
        if self.cleaned_data.get("website"):
            # Deliberately generic — doesn't hint that a honeypot exists.
            raise forms.ValidationError("Registration could not be completed.")
        return ""

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_student_id(self):
        student_id = self.cleaned_data["student_id"].strip()
        if User.objects.filter(student_id__iexact=student_id).exists():
            raise forms.ValidationError("This student ID is already registered.")
        return student_id

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        user.email = self.cleaned_data["email"]
        user.student_id = self.cleaned_data["student_id"]
        if commit:
            user.save()
        return user
