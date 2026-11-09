from django.core.management.base import BaseCommand, CommandError

from copilot.reconciliation import inventory_index_issues, repair_index_issues


class Command(BaseCommand):
    help = "Bounded dry-run-first retrieval-index reconciliation."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--repair", action="store_true")

    def handle(self, *args, **options):
        try:
            issues, cursor, complete = inventory_index_issues(limit=options["limit"])
            repaired = repair_index_issues(issues=issues, limit=options["limit"]) if options["repair"] else 0
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        for issue in issues:
            self.stdout.write(f"issue={issue.code} document={issue.document_id} version={issue.version_id}")
        self.stdout.write(f"issues={len(issues)} repaired={repaired} complete={str(complete).lower()} cursor={cursor or ''}")
