from django.core.management.base import BaseCommand
from axes.models import AccessAttempt


class Command(BaseCommand):
    help = "Reset failed login attempts in the configured database."

    def handle(self, *args, **options):
        deleted, _ = AccessAttempt.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Reset completed. Deleted {deleted} failed-attempt records."
            )
        )