import time
import uuid

from django.core.management.base import BaseCommand, CommandError

from documents.processor import process_one


class Command(BaseCommand):
    help = "Process private document extraction jobs"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Exit after one claim attempt")
        parser.add_argument("--max-jobs", type=int, default=None, help="Exit after this many processed jobs")
        parser.add_argument("--poll-seconds", type=float, default=2.0)

    def handle(self, *args, **options):
        if options["max_jobs"] is not None and options["max_jobs"] <= 0:
            raise CommandError("--max-jobs must be positive")
        if options["poll_seconds"] <= 0 or options["poll_seconds"] > 60:
            raise CommandError("--poll-seconds must be between 0 and 60")
        worker_id = uuid.uuid4()
        processed = 0
        while True:
            outcome = process_one(worker_id=worker_id)
            if outcome is not None:
                processed += 1
                self.stdout.write(f"document_job outcome={outcome} count={processed}")
            if options["once"] or (options["max_jobs"] is not None and processed >= options["max_jobs"]):
                return
            if outcome is None:
                time.sleep(options["poll_seconds"])
