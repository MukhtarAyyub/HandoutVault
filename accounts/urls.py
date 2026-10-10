"""
accounts.urls — mounted at /accounts/ (see config/urls.py).

    /accounts/register/   StudentRegistrationForm (accounts.views.register)
    /accounts/login/      Django's built-in LoginView, our template + form
    /accounts/logout/     Django's built-in LogoutView
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import StyledAuthenticationForm

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=StyledAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
