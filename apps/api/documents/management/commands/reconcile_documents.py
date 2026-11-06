from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from accounts.models import User
from documents.inventory import InventoryCursorError, InventoryWorkLimitError, inventory_recovery_page
from documents.reconciliation import execute_recovery_issue, validate_recovery_actor
from documents.storage import ArtifactStorageError


class Command(BaseCommand):
    help = "Inventory and reconcile private document artifacts/jobs (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--work-limit", type=int, default=5000)
        parser.add_argument("--cursor")
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        if options["limit"] < 1 or options["limit"] > 1000: raise CommandError("Limit must be between 1 and 1000")
        try: actor = validate_recovery_actor(User.objects.get(pk=options["actor_id"]))
        except (User.DoesNotExist, ValueError) as exc: raise CommandError("Recovery actor must be an active, activated App Admin") from exc
        try:
            page = inventory_recovery_page(
                actor_id=actor.pk,
                findings_limit=options["limit"],
                work_limit=options["work_limit"],
                cursor=options["cursor"],
            )
        except (InventoryCursorError, InventoryWorkLimitError, ArtifactStorageError, DatabaseError) as exc:
            raise CommandError(str(exc)) from exc
        issues = page.issues
        status = f"findings={len(issues)} work={page.work_performed} complete={str(page.complete).lower()}"
        if not options["execute"]:
            self.stdout.write(f"DRY RUN: {status}; no changes made.")
            for issue in issues: self.stdout.write(f"{issue.kind} id={issue.identifier if issue.kind != 'orphan_artifact' else 'opaque'}")
            if page.next_cursor: self.stdout.write(f"CONTINUATION: {page.next_cursor}")
            return
        counts = {}
        for issue in issues:
            outcome = execute_recovery_issue(actor=actor, issue=issue); counts[outcome] = counts.get(outcome, 0) + 1
        self.stdout.write(self.style.SUCCESS("Completed page: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))))
        self.stdout.write(status)
        if page.next_cursor: self.stdout.write(f"CONTINUATION: {page.next_cursor}")
