from datetime import date

from django.core.management.base import BaseCommand

from requests.automation import run_request_automations


class Command(BaseCommand):
    help = "Run scheduled request automations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--today",
            help="Override current date in YYYY-MM-DD format.",
        )

    def handle(self, *args, **options):
        today = date.fromisoformat(options["today"]) if options.get("today") else None
        summary = run_request_automations(today=today)
        self.stdout.write(self.style.SUCCESS(f"Request automations completed: {summary.as_dict()}"))
