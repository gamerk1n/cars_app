from django.core.management.base import BaseCommand

from integrations.outbox import dispatch_pending_events


class Command(BaseCommand):
    help = "Dispatch pending outbound integration events."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        summary = dispatch_pending_events(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Integration dispatch completed: {summary.as_dict()}"))
