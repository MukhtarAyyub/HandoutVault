"""
academics.urls — mounted at /catalog/ (see config/urls.py).

    /catalog/<faculty>/                    department_list
    /catalog/<faculty>/<department>/       course_list

("academics" is the Python app/package name — internal, for the code
that models the Faculty/Department/Course hierarchy. "/catalog/" is the
public-facing URL — what a student actually sees in the address bar.
The two don't have to match, and here they intentionally don't: renaming
the app later would be a real refactor, renaming the URL prefix is a
one-line change.)
"""
from django.urls import path

from . import views

app_name = "academics"

urlpatterns = [
    path("<slug:faculty_slug>/", views.department_list, name="department_list"),
    path("<slug:faculty_slug>/<slug:department_slug>/", views.course_list, name="course_list"),
]
