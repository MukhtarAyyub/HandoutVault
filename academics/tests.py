"""
academics.tests
================
Small but not nothing: slug auto-generation is easy to break silently
(e.g. by adding a required field to Faculty/Department that isn't
passed when a slug-less instance is created), and the drill-down views
are the main path a student uses to reach materials without searching.

Run with:  python manage.py test academics
"""
from django.test import TestCase
from django.urls import reverse

from .models import Course, Department, Faculty


class SlugGenerationTests(TestCase):
    def test_faculty_slug_is_generated_from_name(self):
        faculty = Faculty.objects.create(name="Faculty of Computing")
        self.assertEqual(faculty.slug, "faculty-of-computing")

    def test_department_slug_is_generated_from_name(self):
        faculty = Faculty.objects.create(name="Faculty of Computing")
        department = Department.objects.create(faculty=faculty, name="Software Engineering")
        self.assertEqual(department.slug, "software-engineering")

    def test_explicit_slug_is_not_overwritten(self):
        faculty = Faculty.objects.create(name="Faculty of Computing", slug="fac-computing")
        self.assertEqual(faculty.slug, "fac-computing")


class BrowseViewTests(TestCase):
    def setUp(self):
        self.faculty = Faculty.objects.create(name="Faculty of Computing")
        self.department = Department.objects.create(faculty=self.faculty, name="Software Engineering")
        Course.objects.create(department=self.department, code="SWE201", title="Software Requirements")

    def test_department_list_shows_departments_for_that_faculty_only(self):
        other_faculty = Faculty.objects.create(name="Faculty of Arts")
        Department.objects.create(faculty=other_faculty, name="History")

        response = self.client.get(reverse("academics:department_list", args=[self.faculty.slug]))
        self.assertEqual(response.status_code, 200)
        departments = list(response.context["departments"])
        self.assertEqual(departments, [self.department])

    def test_course_list_shows_courses_for_that_department(self):
        response = self.client.get(
            reverse("academics:course_list", args=[self.faculty.slug, self.department.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["courses"].count(), 1)

    def test_unknown_faculty_slug_404s(self):
        response = self.client.get(reverse("academics:department_list", args=["does-not-exist"]))
        self.assertEqual(response.status_code, 404)
