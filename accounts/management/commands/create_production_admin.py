import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the initial HandoutVault production administrator."

    def handle(self, *args, **options):
        username = os.environ.get("INITIAL_ADMIN_USERNAME", "").strip()
        email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip()
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")

        if not username or not email or not password:
            raise CommandError(
                "Set INITIAL_ADMIN_USERNAME, INITIAL_ADMIN_EMAIL, "
                "and INITIAL_ADMIN_PASSWORD."
            )

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        user.email = email
        user.role = User.Role.ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} administrator account: {username}"
            )
        )
