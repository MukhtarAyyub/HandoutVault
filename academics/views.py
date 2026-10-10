"""
academics.views
================
Read-only "drill-down" browsing: Faculty -> Department -> Course. Both
views are public (no @login_required) since browsing the catalog
structure itself isn't sensitive — only the files behind it require an
account, enforced in materials.views.material_download.

Selecting a course from course_list.html hands off to
materials.views.material_list with ?course=<id>, so the actual materials
listing (search, filtering, pagination) has exactly one implementation.
"""
from django.shortcuts import get_object_or_404, render

from .models import Department, Faculty


def department_list(request, faculty_slug):
    faculty = get_object_or_404(Faculty, slug=faculty_slug)
    departments = faculty.departments.all()
    return render(
        request,
        "academics/department_list.html",
        {"faculty": faculty, "departments": departments},
    )


def course_list(request, faculty_slug, department_slug):
    department = get_object_or_404(Department, slug=department_slug, faculty__slug=faculty_slug)
    courses = department.courses.all()
    return render(
        request,
        "academics/course_list.html",
        {"department": department, "courses": courses},
    )
