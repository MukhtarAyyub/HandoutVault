"""
accounts.views
==============
Only one custom view lives here: public self-registration for students.

Login and logout are handled entirely by Django's built-in
`django.contrib.auth.views.LoginView` / `LogoutView`, wired up in
accounts/urls.py with our own templates — there was nothing
project-specific to add there, so we didn't write custom views for them.
"""
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import StudentRegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()

            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )

            messages.success(
                request,
                f"Welcome, {user.first_name}! Your account has been created."
            )

            return redirect("home")
    else:
        form = StudentRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})