"""
accounts.tests
===============
Covers the spec's "Authentication" checklist (blueprint section 24):
registration, login, logout, invalid credentials — plus the
role/is_staff sync in User.save() that gives Admin accounts access to
/admin/ automatically.

Run with:  python manage.py test accounts
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

VALID_REGISTRATION = {
    "first_name": "Amina",
    "last_name": "Bello",
    "student_id": "TSU/CSC/2023/014",
    "email": "amina.bello@example.edu",
    "username": "aminabello",
    "password1": "a-very-unguessable-pass123",
    "password2": "a-very-unguessable-pass123",
}


class RegistrationTests(TestCase):
    def test_registration_creates_a_student_account(self):
        response = self.client.post(reverse("accounts:register"), VALID_REGISTRATION)
        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username="aminabello")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertEqual(user.student_id, "TSU/CSC/2023/014")
        self.assertFalse(user.is_staff)  # students never get admin-site access

    def test_registration_logs_the_new_user_in(self):
        self.client.post(reverse("accounts:register"), VALID_REGISTRATION)
        response = self.client.get(reverse("home"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_duplicate_email_rejected(self):
        User.objects.create_user(username="existing", email="amina.bello@example.edu", password="whatever123")
        response = self.client.post(reverse("accounts:register"), VALID_REGISTRATION)
        self.assertEqual(response.status_code, 200)  # form redisplayed with an error
        self.assertFalse(User.objects.filter(username="aminabello").exists())

    def test_duplicate_student_id_rejected(self):
        User.objects.create_user(username="existing", student_id="TSU/CSC/2023/014", password="whatever123")
        response = self.client.post(reverse("accounts:register"), VALID_REGISTRATION)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="aminabello").exists())


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="aminabello", password="a-very-unguessable-pass123")

    def test_valid_credentials_log_in(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "aminabello", "password": "a-very-unguessable-pass123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_password_is_rejected(self):
        response = self.client.post(reverse("accounts:login"), {"username": "aminabello", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout(self):
        self.client.force_login(self.user)
        self.client.post(reverse("accounts:logout"))
        response = self.client.get(reverse("bookmarks:bookmark_list"))
        self.assertEqual(response.status_code, 302)  # login_required kicks in again


class RolePromotionTests(TestCase):
    def test_admin_role_grants_staff_access(self):
        user = User.objects.create_user(username="registrar", password="whatever123", role=User.Role.STUDENT)
        self.assertFalse(user.is_staff)

        user.role = User.Role.ADMIN
        user.save()
        user.refresh_from_db()
        self.assertTrue(user.is_staff)


class BotProtectionTests(TestCase):
    """SECURITY.md, "Add bot protection" — the registration honeypot field."""

    def test_filling_the_honeypot_rejects_registration(self):
        data = dict(VALID_REGISTRATION, website="https://spam.example.com")
        response = self.client.post(reverse("accounts:register"), data)
        self.assertEqual(response.status_code, 200)  # re-rendered with an error, not redirected
        self.assertFalse(User.objects.filter(username="aminabello").exists())

    def test_leaving_the_honeypot_blank_still_registers(self):
        response = self.client.post(reverse("accounts:register"), VALID_REGISTRATION)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="aminabello").exists())


class LoginRateLimitTests(TestCase):
    """SECURITY.md, "Rate limit login" — django-axes locks out repeated failures."""

    def setUp(self):
        self.user = User.objects.create_user(username="targetuser", password="correct-horse-battery-staple")

    def test_repeated_failures_lock_out_further_attempts(self):
        from django.conf import settings as django_settings

        limit = getattr(django_settings, "AXES_FAILURE_LIMIT", 5)
        for _ in range(limit):
            self.client.post(reverse("accounts:login"), {"username": "targetuser", "password": "wrong"})

        # Even the CORRECT password should now be refused for a while — that's the point:
        # it's the account/IP combination being throttled, not just bad passwords failing.
        response = self.client.post(
            reverse("accounts:login"), {"username": "targetuser", "password": "correct-horse-battery-staple"}
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
