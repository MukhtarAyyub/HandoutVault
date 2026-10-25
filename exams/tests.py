"""
exams.tests
===========
Exam Preparation end to end: the login gate, Admin-only management, listing
and filtering, downloads, and the link between a summary and its handout.

Run with:  python manage.py test exams
"""
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from academics.models import AcademicSession, Course, Department, Faculty, Semester
from materials.models import Material

from .models import PastQuestion, Summary

User = get_user_model()


def pdf(name="paper.pdf"):
    """A minimal in-memory file with a genuine PDF signature (the upload validator checks content)."""
    return SimpleUploadedFile(name, b"%PDF-1.4\n" + b"0" * 512, content_type="application/pdf")


class ExamTestCase(TestCase):
    """Shared fixtures: one faculty/department with two courses, a handout, an Admin and a Student."""

    def setUp(self):
        self.faculty = Faculty.objects.create(name="Faculty of Computing")
        self.department = Department.objects.create(faculty=self.faculty, name="Software Engineering")
        self.course = Course.objects.create(department=self.department, code="SWE201", title="Software Requirements")
        self.other_course = Course.objects.create(department=self.department, code="SWE301", title="Software Design")
        self.semester = Semester.objects.create(name=Semester.Term.FIRST)
        self.session = AcademicSession.objects.create(name="2025/2026")
        self.admin = User.objects.create_user(username="admin1", password="pw-12345-xyz", role=User.Role.ADMIN)
        self.student = User.objects.create_user(
            username="student1", password="pw-12345-xyz", role=User.Role.STUDENT, student_id="S/001"
        )
        self.handout = Material(
            title="Lecture 3", course=self.course, level=200, semester=self.semester,
            session=self.session, uploaded_by=self.admin,
        )
        self.handout.file = pdf("lecture.pdf")
        self.handout.save()

    def make(self, model, **overrides):
        """Create a PastQuestion/Summary straight through the ORM."""
        item = model(
            title=overrides.pop("title", "Item"),
            course=overrides.pop("course", self.course),
            level=overrides.pop("level", 200),
            semester=self.semester,
            session=self.session,
            uploaded_by=self.admin,
            **overrides,
        )
        item.file = pdf()
        item.save()
        return item

    def form_data(self, **overrides):
        """A valid POST body for the add/edit forms (what a browser would submit)."""
        data = {
            "title": "2024 Final Exam", "course": self.course.id, "level": 200,
            "semester": self.semester.id, "session": self.session.id,
            "description": "", "file": pdf("exam.pdf"),
        }
        data.update(overrides)
        return data


class LoginGateTests(ExamTestCase):
    """Tapping "Exam Preparation" while signed out goes to the login page first, then back."""

    def test_hub_sends_anonymous_visitors_to_login_with_a_way_back(self):
        url = reverse("exams:hub")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False)

    def test_logging_in_returns_to_exam_preparation(self):
        url = reverse("exams:hub")
        response = self.client.post(
            reverse("accounts:login"), {"username": "student1", "password": "pw-12345-xyz", "next": url}
        )
        self.assertRedirects(response, url, fetch_redirect_response=False)

    def test_every_exam_page_needs_a_login(self):
        pq = self.make(PastQuestion)
        for url in (
            reverse("exams:list", args=["past-questions"]),
            reverse("exams:list", args=["summaries"]),
            pq.get_absolute_url(),
            reverse("exams:download", args=["past-questions", pq.pk]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_home_page_has_the_exam_preparation_button(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'href="%s"' % reverse("exams:hub"))
        self.assertContains(response, "Exam Preparation")


class StudentAccessTests(ExamTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)
        self.pq = self.make(PastQuestion, title="2024 Final Exam")

    def test_hub_lists_both_sections_with_counts(self):
        response = self.client.get(reverse("exams:hub"))
        self.assertEqual(response.status_code, 200)
        counts = {s["kind"].slug: s["count"] for s in response.context["sections"]}
        self.assertEqual(counts, {"past-questions": 1, "summaries": 0})

    def test_student_can_open_and_download(self):
        self.assertEqual(self.client.get(self.pq.get_absolute_url()).status_code, 200)
        response = self.client.get(reverse("exams:download", args=["past-questions", self.pq.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        b"".join(response.streaming_content)  # drain the stream so the file handle closes
        self.pq.refresh_from_db()
        self.assertEqual(self.pq.download_count, 1)

    def test_student_cannot_add_edit_or_delete(self):
        urls = [
            reverse("exams:add", args=["past-questions"]),
            reverse("exams:edit", args=["past-questions", self.pq.pk]),
            reverse("exams:delete", args=["past-questions", self.pq.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(urls[2]).status_code, 403)
        self.assertTrue(PastQuestion.objects.filter(pk=self.pq.pk).exists())

    def test_unknown_section_is_a_404(self):
        self.assertEqual(self.client.get("/exam-prep/nonsense/").status_code, 404)


class AdminManagementTests(ExamTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_admin_adds_a_past_question(self):
        response = self.client.post(reverse("exams:add", args=["past-questions"]), self.form_data())
        self.assertEqual(response.status_code, 302)
        pq = PastQuestion.objects.get(title="2024 Final Exam")
        self.assertEqual(pq.uploaded_by, self.admin)
        self.assertEqual(pq.file_type, "pdf")
        self.assertRedirects(response, pq.get_absolute_url(), fetch_redirect_response=False)

    def test_admin_adds_a_summary_linked_to_a_handout(self):
        response = self.client.post(
            reverse("exams:add", args=["summaries"]),
            self.form_data(title="Lecture 3 in one page", handout=self.handout.id),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Summary.objects.get().handout, self.handout)

    def test_summary_handout_must_be_from_the_same_course(self):
        response = self.client.post(
            reverse("exams:add", args=["summaries"]),
            self.form_data(course=self.other_course.id, handout=self.handout.id),
        )
        self.assertEqual(response.status_code, 200)  # form shown again with an error
        self.assertIn("handout", response.context["form"].errors)
        self.assertEqual(Summary.objects.count(), 0)

    def test_add_form_is_prefilled_from_a_handout(self):
        response = self.client.get(reverse("exams:add", args=["summaries"]) + f"?handout={self.handout.id}")
        initial = response.context["form"].initial
        self.assertEqual(initial["handout"], self.handout)
        self.assertEqual(initial["course"], self.course)
        self.assertEqual(initial["title"], "Summary: Lecture 3")

    def test_uploads_get_the_same_strict_file_checks_as_handouts(self):
        url = reverse("exams:add", args=["past-questions"])
        bad_extension = SimpleUploadedFile("virus.exe", b"MZ...", content_type="application/octet-stream")
        fake_pdf = SimpleUploadedFile("fake.pdf", b"this is not a pdf", content_type="application/pdf")
        for upload in (bad_extension, fake_pdf):
            with self.subTest(file=upload.name):
                response = self.client.post(url, self.form_data(file=upload))
                self.assertEqual(response.status_code, 200)
        self.assertEqual(PastQuestion.objects.count(), 0)

    def test_admin_edits_and_deletes(self):
        pq = self.make(PastQuestion, title="Old title")
        edit_url = reverse("exams:edit", args=["past-questions", pq.pk])
        response = self.client.post(edit_url, self.form_data(title="New title"))
        self.assertEqual(response.status_code, 302)
        pq.refresh_from_db()
        self.assertEqual(pq.title, "New title")

        stored_name = pq.file.name
        self.assertTrue(default_storage.exists(stored_name))
        delete_url = reverse("exams:delete", args=["past-questions", pq.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 200)  # confirmation page, nothing deleted yet
        self.assertTrue(PastQuestion.objects.filter(pk=pq.pk).exists())
        self.assertEqual(self.client.post(delete_url).status_code, 302)
        self.assertFalse(PastQuestion.objects.filter(pk=pq.pk).exists())
        self.assertFalse(default_storage.exists(stored_name))


class StoragePathTests(ExamTestCase):
    def test_course_code_and_session_are_slugified_in_the_storage_path(self):
        messy = Course.objects.create(department=self.department, code="CSE  201", title="Messy")
        pq = self.make(PastQuestion, course=messy)
        self.assertTrue(pq.file.name.startswith("exam-prep/past-questions/cse-201/2025-2026/"), pq.file.name)


class ListFilterTests(ExamTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)
        self.a = self.make(PastQuestion, title="Alpha paper", course=self.course, level=200)
        self.b = self.make(PastQuestion, title="Beta paper", course=self.other_course, level=300)
        self.url = reverse("exams:list", args=["past-questions"])

    def results(self, **params):
        return list(self.client.get(self.url, params).context["page_obj"])

    def test_filters_combine_and_narrow(self):
        self.assertCountEqual(self.results(), [self.a, self.b])
        self.assertEqual(self.results(course=self.other_course.id), [self.b])
        self.assertEqual(self.results(level=200), [self.a])
        self.assertEqual(self.results(department=self.department.id, level=300), [self.b])
        self.assertCountEqual(self.results(faculty=self.faculty.id), [self.a, self.b])

    def test_search_matches_title_and_course_code(self):
        self.assertEqual(self.results(q="Alpha"), [self.a])
        self.assertEqual(self.results(q="SWE301"), [self.b])

    def test_bad_filter_values_are_ignored_not_errors(self):
        response = self.client.get(self.url, {"course": "abc", "level": "x' OR 1=1", "page": "zzz"})
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context["page_obj"], [self.a, self.b])

    def test_summary_search_also_looks_at_the_handout_title(self):
        summary = self.make(Summary, title="One-pager", handout=self.handout)
        response = self.client.get(reverse("exams:list", args=["summaries"]), {"q": "Lecture 3"})
        self.assertEqual(list(response.context["page_obj"]), [summary])

    def test_course_filter_shows_the_handouts_pastquestions_summaries_switcher(self):
        response = self.client.get(self.url, {"course": self.course.id})
        self.assertEqual(response.context["course_obj"], self.course)
        self.assertEqual(response.context["course_counts"], {"handouts": 1, "past_questions": 1, "summaries": 0})


class HandoutLinkTests(ExamTestCase):
    def test_handout_page_lists_its_summaries_for_signed_in_users_only(self):
        summary = self.make(Summary, title="Lecture 3 in one page", handout=self.handout)
        url = self.handout.get_absolute_url()
        self.assertNotContains(self.client.get(url), "Lecture 3 in one page")  # anonymous: only a login prompt
        self.client.force_login(self.student)
        self.assertContains(self.client.get(url), "Lecture 3 in one page")
        self.assertContains(self.client.get(url), summary.get_absolute_url())

    def test_handout_list_filtered_to_a_course_has_the_switcher(self):
        self.make(PastQuestion)
        response = self.client.get(reverse("materials:material_list"), {"course": self.course.id})
        self.assertEqual(response.context["course_counts"], {"handouts": 1, "past_questions": 1, "summaries": 0})

    def test_deleting_a_handout_keeps_its_summary(self):
        summary = self.make(Summary, handout=self.handout)
        self.handout.delete()
        summary.refresh_from_db()
        self.assertIsNone(summary.handout)

    def test_dashboard_counts_exam_content(self):
        self.make(PastQuestion)
        self.make(Summary)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("materials:admin_dashboard"))
        self.assertEqual(response.context["total_past_questions"], 1)
        self.assertEqual(response.context["total_summaries"], 1)
