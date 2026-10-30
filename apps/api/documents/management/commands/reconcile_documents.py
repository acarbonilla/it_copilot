from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from documents.reconciliation import execute_recovery_issue, inventory_recovery_issues, validate_recovery_actor


class Command(BaseCommand):
    help = "Inventory and reconcile private document artifacts/jobs (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        if options["limit"] < 1 or options["limit"] > 1000: raise CommandError("Limit must be between 1 and 1000")
        try: actor = validate_recovery_actor(User.objects.get(pk=options["actor_id"]))
        except (User.DoesNotExist, ValueError) as exc: raise CommandError("Recovery actor must be an active, activated App Admin") from exc
        issues = inventory_recovery_issues(limit=options["limit"])
        if not options["execute"]:
            self.stdout.write(f"DRY RUN: {len(issues)} issue(s); no changes made.")
            for issue in issues: self.stdout.write(f"{issue.kind} id={issue.identifier if issue.kind != 'orphan_artifact' else 'opaque'}")
            return
        counts = {}
        for issue in issues:
            outcome = execute_recovery_issue(actor=actor, issue=issue); counts[outcome] = counts.get(outcome, 0) + 1
        self.stdout.write(self.style.SUCCESS("Completed: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))))
