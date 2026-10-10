"""
materials.tests
================
Automated coverage for the spec's own "Testing" checklist (blueprint
section 24): permission boundaries (who can reach which view) and
file-upload validation (extension whitelist, size limit). Search/filter
behavior is covered too, since material_list's query-param handling is
easy to silently break while editing it.

Manual-only items from that checklist — different screen sizes, slow
connections — aren't things a unit test can meaningfully assert; see
README.md's testing section for the manual QA pass instead.

Run with:  python manage.py test materials
"""
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from academics.models import AcademicSession, Course, Department, Faculty, Semester

from .models import Download, Material

User = get_user_model()


def make_pdf(name="lecture.pdf", size_bytes=1024):
    """A minimal in-memory file that passes the extension check without touching disk."""
    content = b"%PDF-1.4\n" + (b"0" * max(0, size_bytes - 9))
    return SimpleUploadedFile(name, content, content_type="application/pdf")


_OOXML_MARKER_BY_EXT = {
    "docx": "word/document.xml",
    "pptx": "ppt/presentation.xml",
    "xlsx": "xl/workbook.xml",
}
_OOXML_CONTENT_TYPE = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def make_ooxml(ext, name=None):
    """
    A real (if minimal) .docx/.pptx/.xlsx: an actual ZIP containing
    [Content_Types].xml plus the one marker file materials.validators
    checks for that extension. Needed because that validator now
    verifies content, not just the filename — see
    materials.validators._looks_like_ooxml.
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(_OOXML_MARKER_BY_EXT[ext], "<root/>")
    buffer.seek(0)
    return SimpleUploadedFile(name or f"file.{ext}", buffer.read(), content_type=_OOXML_CONTENT_TYPE[ext])


class MaterialsTestCase(TestCase):
    """Shared fixtures: one faculty/department/course/semester/session, one admin, one student."""

    def setUp(self):
        self.faculty = Faculty.objects.create(name="Faculty of Computing")
        self.department = Department.objects.create(faculty=self.faculty, name="Software Engineering")
        self.course = Course.objects.create(department=self.department, code="SWE201", title="Software Requirements")
        self.semester = Semester.objects.create(name=Semester.Term.FIRST)
        self.session = AcademicSession.objects.create(name="2026/2027")

        self.admin = User.objects.create_user(username="admin1", password="strongpass123", role=User.Role.ADMIN)
        self.student = User.objects.create_user(
            username="student1", password="strongpass123", role=User.Role.STUDENT, student_id="TSU/CSC/001"
        )

    def upload_material(self, **overrides):
        """Create a Material directly (bypassing the view/form) for tests that need one to already exist."""
        material = Material(
            title=overrides.get("title", "Lecture 3"),
            course=overrides.get("course", self.course),
            level=overrides.get("level", Material.Level.L200),
            semester=overrides.get("semester", self.semester),
            session=overrides.get("session", self.session),
            topic=overrides.get("topic", "Requirements Engineering"),
            uploaded_by=self.admin,
        )
        material.file = overrides.get("file", make_pdf())
        material.save()
        return material

    def upload_form_data(self, **overrides):
        """Base POST payload for material_upload/material_edit, matching a real form submission."""
        data = {
            "title": "Lecture 4",
            "course": self.course.id,
            "level": 200,
            "semester": self.semester.id,
            "session": self.session.id,
            "topic": "Elicitation",
            "week": 4,
            "description": "",
            "file": make_pdf("lecture4.pdf"),
        }
        data.update(overrides)
        return data


class PermissionTests(MaterialsTestCase):
    """Spec section 24, "Permissions": Student -> denied, Admin -> allowed."""

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("materials:material_upload"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_student_cannot_reach_upload(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("materials:material_upload"))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_reach_dashboard(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("materials:admin_dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_delete(self):
        material = self.upload_material()
        self.client.force_login(self.student)
        response = self.client.post(reverse("materials:material_delete", args=[material.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Material.objects.filter(pk=material.pk).exists())

    def test_admin_can_upload(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("materials:material_upload"), self.upload_form_data())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Material.objects.filter(title="Lecture 4").exists())

    def test_admin_can_delete(self):
        material = self.upload_material()
        self.client.force_login(self.admin)
        response = self.client.post(reverse("materials:material_delete", args=[material.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Material.objects.filter(pk=material.pk).exists())


class UploadValidationTests(MaterialsTestCase):
    """Spec section 6/24: reject disallowed extensions and oversized files."""

    def test_pptx_and_docx_are_accepted(self):
        self.client.force_login(self.admin)
        for ext in ["pptx", "docx"]:
            response = self.client.post(
                reverse("materials:material_upload"),
                self.upload_form_data(title=f"File as {ext}", file=make_ooxml(ext)),
            )
            self.assertEqual(response.status_code, 302, f"{ext} upload should succeed")
        self.assertEqual(Material.objects.filter(title__startswith="File as").count(), 2)

    def test_ooxml_file_with_wrong_internal_structure_is_rejected(self):
        """A .docx that's a real zip but not really a Word document (e.g. a renamed .xlsx)."""
        self.client.force_login(self.admin)
        mislabeled = make_ooxml("xlsx", name="not-really-a.docx")
        response = self.client.post(
            reverse("materials:material_upload"),
            self.upload_form_data(title="Mislabeled file", file=mislabeled),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Material.objects.filter(title="Mislabeled file").exists())

    def test_disallowed_extension_rejected(self):
        self.client.force_login(self.admin)
        bad_file = SimpleUploadedFile("virus.exe", b"not really a virus", content_type="application/octet-stream")
        response = self.client.post(
            reverse("materials:material_upload"),
            self.upload_form_data(title="Bad file", file=bad_file),
        )
        self.assertEqual(response.status_code, 200)  # form re-rendered with an error, not redirected
        self.assertFalse(Material.objects.filter(title="Bad file").exists())

    @override_settings(MAX_MATERIAL_UPLOAD_MB=1)
    def test_oversized_file_rejected(self):
        self.client.force_login(self.admin)
        oversized = make_pdf("big.pdf", size_bytes=2 * 1024 * 1024)  # 2 MB against a 1 MB test limit
        response = self.client.post(
            reverse("materials:material_upload"),
            self.upload_form_data(title="Too big", file=oversized),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Material.objects.filter(title="Too big").exists())


class DownloadTests(MaterialsTestCase):
    """Spec section 24: downloads work, and require an account so they can be logged."""

    def test_download_requires_login(self):
        material = self.upload_material()
        response = self.client.get(reverse("materials:material_download", args=[material.pk]))
        self.assertEqual(response.status_code, 302)

    def test_download_logs_and_streams(self):
        material = self.upload_material()
        self.client.force_login(self.student)
        response = self.client.get(reverse("materials:material_download", args=[material.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Download.objects.filter(material=material, student=self.student).count(), 1)
        self.assertEqual(material.download_count, 1)


class SearchAndFilterTests(MaterialsTestCase):
    """Spec section 24, "Search": course code, topic, department/level filtering."""

    def setUp(self):
        super().setUp()
        self.material = self.upload_material(title="Requirements Elicitation", topic="Elicitation")

        arts_faculty = Faculty.objects.create(name="Faculty of Arts")
        history_dept = Department.objects.create(faculty=arts_faculty, name="History")
        history_course = Course.objects.create(department=history_dept, code="HIS101", title="World History")
        self.other_material = self.upload_material(
            title="Ancient Civilizations",
            topic="Mesopotamia",
            course=history_course,
            level=Material.Level.L100,
        )
        self.arts_faculty = arts_faculty

    def test_search_by_course_code(self):
        response = self.client.get(reverse("materials:material_list"), {"q": "SWE201"})
        results = list(response.context["page_obj"])
        self.assertIn(self.material, results)
        self.assertNotIn(self.other_material, results)

    def test_search_by_topic(self):
        response = self.client.get(reverse("materials:material_list"), {"q": "Mesopotamia"})
        results = list(response.context["page_obj"])
        self.assertIn(self.other_material, results)
        self.assertNotIn(self.material, results)

    def test_filter_by_level(self):
        response = self.client.get(reverse("materials:material_list"), {"level": 100})
        results = list(response.context["page_obj"])
        self.assertIn(self.other_material, results)
        self.assertNotIn(self.material, results)

    def test_filter_by_faculty(self):
        response = self.client.get(reverse("materials:material_list"), {"faculty": self.arts_faculty.slug})
        results = list(response.context["page_obj"])
        self.assertIn(self.other_material, results)
        self.assertNotIn(self.material, results)

    def test_malformed_numeric_filter_is_ignored_not_500(self):
        """?level=abc should behave like no level filter at all, not crash the page."""
        response = self.client.get(reverse("materials:material_list"), {"level": "abc"})
        self.assertEqual(response.status_code, 200)
        results = list(response.context["page_obj"])
        self.assertIn(self.material, results)
        self.assertIn(self.other_material, results)
