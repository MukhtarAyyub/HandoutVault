"""
config.test_pages
=================
UI smoke tests. Every page of the site renders (HTTP 200) for the roles that
may see it, and none of them contains anything the site's strict
Content-Security-Policy would silently block: inline event handlers
(onchange=...), inline <script> blocks, or inline style="" attributes. A
page that works in these tests also works in a browser behind that policy.

Also guards the stylesheet: the static-files "manifest" storage used in
production fails the whole `collectstatic` if a CSS url() points at a file
that doesn't exist, so the stylesheet may only use inline data: images.

Run with:  python manage.py test config
"""
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from academics.models import AcademicSession, Course, Department, Faculty, Semester
from bookmarks.models import Bookmark
from exams.models import PastQuestion, Summary
from materials.models import Material

User = get_user_model()


def pdf(name="file.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + b"0" * 256, content_type="application/pdf")


class PageRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.faculty = Faculty.objects.create(name="Faculty of Computing")
        cls.department = Department.objects.create(faculty=cls.faculty, name="Software Engineering")
        cls.course = Course.objects.create(department=cls.department, code="SWE201", title="Software Requirements")
        cls.semester = Semester.objects.create(name=Semester.Term.FIRST)
        cls.session = AcademicSession.objects.create(name="2025/2026")
        cls.admin = User.objects.create_user(username="admin1", password="pw-12345-xyz", role=User.Role.ADMIN)
        cls.student = User.objects.create_user(username="student1", password="pw-12345-xyz", student_id="S/001")

        shared = dict(course=cls.course, level=200, semester=cls.semester, session=cls.session, uploaded_by=cls.admin)
        cls.handout = Material(title="Lecture 3", topic="Requirements", **shared)
        cls.handout.file = pdf("lecture.pdf")
        cls.handout.save()
        cls.pq = PastQuestion(title="2024 Final Exam", **shared)
        cls.pq.file = pdf("exam.pdf")
        cls.pq.save()
        cls.summary = Summary(title="Lecture 3 in one page", handout=cls.handout, **shared)
        cls.summary.file = pdf("summary.pdf")
        cls.summary.save()
        Bookmark.objects.create(student=cls.student, material=cls.handout)

    def assertRenders(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        html = response.content.decode()
        self.assertNotRegex(html, r"\son[a-z]+\s*=", f"inline event handler on {url}")
        self.assertNotRegex(html, r"\sstyle\s*=", f"inline style attribute on {url}")
        self.assertNotRegex(html, r"<script(?![^>]*\ssrc=)", f"inline <script> on {url}")
        self.assertContains(response, "HandoutVault")
        # Template comments / tags that leaked into the output (a multi-line {# #} comment is NOT a
        # comment in Django - it prints as text) and anything before <!DOCTYPE>, which puts the
        # browser into quirks mode and breaks the layout.
        self.assertNotIn("{#", html, f"leaked template comment on {url}")
        self.assertNotIn("{%", html, f"leaked template tag on {url}")
        self.assertTrue(html.startswith("<!DOCTYPE html>"), f"output before <!DOCTYPE> on {url}: {html[:60]!r}")
        return response

    def test_public_pages(self):
        self.assertRenders(reverse("home"))
        self.assertRenders(reverse("materials:material_list"))
        self.assertRenders(reverse("materials:material_list") + f"?course={self.course.id}&q=lecture&level=200")
        self.assertRenders(self.handout.get_absolute_url())
        self.assertRenders(reverse("accounts:login") + "?next=/exam-prep/")
        self.assertRenders(reverse("accounts:register"))
        self.assertRenders(reverse("academics:department_list", args=[self.faculty.slug]))
        self.assertRenders(reverse("academics:course_list", args=[self.faculty.slug, self.department.slug]))

    def test_student_pages(self):
        self.client.force_login(self.student)
        self.assertRenders(reverse("home"))
        self.assertRenders(self.handout.get_absolute_url())
        self.assertRenders(reverse("materials:material_list"))
        self.assertRenders(reverse("bookmarks:bookmark_list"))
        self.assertRenders(reverse("exams:hub"))
        for kind, item in (("past-questions", self.pq), ("summaries", self.summary)):
            self.assertRenders(reverse("exams:list", args=[kind]))
            self.assertRenders(reverse("exams:list", args=[kind]) + f"?course={self.course.id}&level=200")
            self.assertRenders(item.get_absolute_url())

    def test_admin_pages(self):
        self.client.force_login(self.admin)
        self.assertRenders(reverse("home"))
        self.assertRenders(reverse("materials:admin_dashboard"))
        self.assertRenders(reverse("materials:material_upload"))
        self.assertRenders(reverse("materials:material_edit", args=[self.handout.pk]))
        self.assertRenders(reverse("materials:material_delete", args=[self.handout.pk]))
        self.assertRenders(self.handout.get_absolute_url())
        self.assertRenders(reverse("exams:hub"))
        for kind, item in (("past-questions", self.pq), ("summaries", self.summary)):
            self.assertRenders(reverse("exams:add", args=[kind]))
            self.assertRenders(reverse("exams:edit", args=[kind, item.pk]))
            self.assertRenders(reverse("exams:delete", args=[kind, item.pk]))
            self.assertRenders(item.get_absolute_url())

    def test_empty_site_still_renders(self):
        """A brand-new deployment (no faculties, no materials) must not error."""
        Material.objects.all().delete(); PastQuestion.objects.all().delete(); Summary.objects.all().delete()
        Faculty.objects.all().delete()
        self.assertRenders(reverse("home"))
        self.assertRenders(reverse("materials:material_list"))
        self.client.force_login(self.student)
        self.assertRenders(reverse("exams:hub"))
        self.assertRenders(reverse("exams:list", args=["summaries"]))


class StylesheetTests(TestCase):
    def test_stylesheet_only_uses_inline_data_images(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "style.css").read_text()
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)  # ignore comments (they mention "url()" in prose)
        urls = re.findall(r"url\(\s*([^)]*?)\s*\)", css)
        self.assertTrue(urls, "expected the select-arrow data: images to be present")
        for value in urls:
            self.assertTrue(value.strip("\"'").startswith("data:"), f"stylesheet references a file: {value[:60]}")

    def test_script_and_stylesheet_exist(self):
        for relative in ("css/style.css", "js/app.js"):
            self.assertTrue((Path(settings.BASE_DIR) / "static" / relative).is_file(), relative)


class SecurityHeaderTests(TestCase):
    def test_other_sites_cannot_frame_us_but_we_can_frame_our_own_files(self):
        """Clickjacking protection stays on (SAMEORIGIN / frame-ancestors 'self'), yet the PDF preview
        <iframe> can load a file served from this same domain."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", response["Content-Security-Policy"])
        self.assertIn("script-src 'self'", response["Content-Security-Policy"])
        self.assertNotIn("script-src 'self' 'unsafe-inline'", response["Content-Security-Policy"])


class LiveUrlStabilityTests(TestCase):
    """
    The site is live: its addresses are printed in QR codes and shared in chats. Every existing
    URL must keep working exactly as before; an update may only ADD routes. If one of these
    assertions ever fails, a link people already have is about to break.
    """

    def test_existing_urls_are_unchanged(self):
        expected = [
            (reverse("home"), "/"),
            (reverse("materials:material_list"), "/materials/"),
            (reverse("materials:material_detail", args=[7]), "/materials/7/"),
            (reverse("materials:material_download", args=[7]), "/materials/7/download/"),
            (reverse("materials:material_upload"), "/materials/upload/"),
            (reverse("materials:material_edit", args=[7]), "/materials/7/edit/"),
            (reverse("materials:material_delete", args=[7]), "/materials/7/delete/"),
            (reverse("materials:admin_dashboard"), "/materials/dashboard/"),
            (reverse("accounts:login"), "/accounts/login/"),
            (reverse("accounts:register"), "/accounts/register/"),
            (reverse("accounts:logout"), "/accounts/logout/"),
            (reverse("bookmarks:bookmark_list"), "/bookmarks/"),
            (reverse("bookmarks:toggle_bookmark", args=[7]), "/bookmarks/toggle/7/"),
            (reverse("academics:department_list", args=["fac"]), "/catalog/fac/"),
            (reverse("academics:course_list", args=["fac", "dept"]), "/catalog/fac/dept/"),
            (reverse("admin:index"), "/admin/"),
            # added by the Exam Preparation update
            (reverse("exams:hub"), "/exam-prep/"),
        ]
        for actual, wanted in expected:
            self.assertEqual(actual, wanted)
