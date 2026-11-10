"""Delete all app data but keep superusers: `python manage.py wipe_data`."""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from accounts.models import School, User
from courses.models import Course


class Command(BaseCommand):
    help = "Delete all schools, courses, users etc. Superusers are kept."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")

    def handle(self, *args, yes=False, **opts):
        db = connection.settings_dict["NAME"]
        if not yes:
            ans = input(f"Wipe all data (except superusers) in '{db}'? Type 'yes': ")
            if ans.strip().lower() != "yes":
                raise CommandError("Cancelled.")
        with transaction.atomic():
            Course.objects.all().delete()  # first: instructor FK is PROTECT
            School.objects.all().delete()  # cascades users, invites
            User.objects.filter(is_superuser=False).delete()  # school-less leftovers
        kept = User.objects.filter(is_superuser=True).values_list("username", flat=True)
        self.stdout.write(self.style.SUCCESS(f"Wiped. Kept superusers: {', '.join(kept) or 'none'}"))
