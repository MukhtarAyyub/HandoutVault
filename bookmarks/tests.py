"""
bookmarks.tests
================
Covers the toggle semantics (add on first POST, remove on second) and
that a student only ever sees their own bookmarks.

Run with:  python manage.py test bookmarks
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from academics.models import AcademicSession, Course, Department, Faculty, Semester
from materials.models import Material

from .models import Bookmark

User = get_user_model()


class BookmarkTests(TestCase):
    def setUp(self):
        faculty = Faculty.objects.create(name="Faculty of Computing")
        department = Department.objects.create(faculty=faculty, name="Software Engineering")
        course = Course.objects.create(department=department, code="SWE201", title="Software Requirements")
        semester = Semester.objects.create(name=Semester.Term.FIRST)
        session = AcademicSession.objects.create(name="2026/2027")

        self.admin = User.objects.create_user(username="admin1", password="strongpass123", role=User.Role.ADMIN)
        self.alice = User.objects.create_user(
            username="alice", password="strongpass123", role=User.Role.STUDENT, student_id="TSU/001"
        )
        self.bob = User.objects.create_user(
            username="bob", password="strongpass123", role=User.Role.STUDENT, student_id="TSU/002"
        )

        self.material = Material(
            title="Lecture 3", course=course, level=Material.Level.L200, semester=semester, session=session,
            uploaded_by=self.admin,
        )
        self.material.file = SimpleUploadedFile("lecture.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        self.material.save()

    def test_toggle_requires_login(self):
        response = self.client.post(reverse("bookmarks:toggle_bookmark", args=[self.material.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Bookmark.objects.count(), 0)

    def test_toggle_requires_post(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("bookmarks:toggle_bookmark", args=[self.material.pk]))
        self.assertEqual(response.status_code, 405)  # GET not allowed on a state-changing view

    def test_first_toggle_bookmarks_second_removes(self):
        self.client.force_login(self.alice)
        url = reverse("bookmarks:toggle_bookmark", args=[self.material.pk])

        self.client.post(url)
        self.assertTrue(Bookmark.objects.filter(student=self.alice, material=self.material).exists())

        self.client.post(url)
        self.assertFalse(Bookmark.objects.filter(student=self.alice, material=self.material).exists())

    def test_bookmark_list_shows_only_own_bookmarks(self):
        Bookmark.objects.create(student=self.alice, material=self.material)
        Bookmark.objects.create(student=self.bob, material=self.material)

        self.client.force_login(self.alice)
        response = self.client.get(reverse("bookmarks:bookmark_list"))
        bookmarks = list(response.context["bookmarks"])

        self.assertEqual(len(bookmarks), 1)
        self.assertEqual(bookmarks[0].student, self.alice)
