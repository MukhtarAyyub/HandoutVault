import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Diagnose the production administrator account."

    def handle(self, *args, **options):
        username = os.environ.get("INITIAL_ADMIN_USERNAME", "").strip()
        password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")

        if not username:
            raise CommandError(
                "Set INITIAL_ADMIN_USERNAME temporarily in Render."
            )

        User = get_user_model()

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"Account exists: NO (username={username})"
            ))
            return

        self.stdout.write(f"Account exists: YES")
        self.stdout.write(f"Active: {user.is_active}")
        self.stdout.write(f"Staff: {user.is_staff}")
        self.stdout.write(f"Superuser: {user.is_superuser}")
        self.stdout.write(f"Admin role: {user.role == User.Role.ADMIN}")

        if password:
            self.stdout.write(
                f"Configured password matches: "
                f"{user.check_password(password)}"
            )
        else:
            self.stdout.write(
                "Password check skipped: no temporary password supplied."
            )