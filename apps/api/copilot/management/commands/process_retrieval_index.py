from django.core.management.base import BaseCommand

from copilot.indexing import process_one_index_job


class Command(BaseCommand):
    help = "Process the bounded retrieval-index queue without logging document content."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--max-jobs", type=int, default=100)

    def handle(self, *args, **options):
        maximum = 1 if options["once"] else options["max_jobs"]
        if maximum < 1 or maximum > 256:
            raise ValueError("max-jobs must be between 1 and 256")
        processed = 0
        for _ in range(maximum):
            outcome = process_one_index_job()
            if outcome is None:
                break
            processed += 1
            self.stdout.write(f"outcome={outcome}")
        self.stdout.write(f"processed={processed}")
