from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from accounts.models import User
from documents.inventory import (
    InventoryCursorError,
    InventoryWorkLimitError,
    assess_ready_consistency_page,
)
from documents.reconciliation import validate_recovery_actor
from documents.storage import ArtifactStorageError


class Command(BaseCommand):
    help = "Run a bounded, read-only READY/current-version consistency assessment."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--work-limit", type=int, default=5000)
        parser.add_argument("--cursor")
        parser.add_argument("--check-physical", action="store_true")

    def handle(self, *args, **options):
        try:
            actor = validate_recovery_actor(User.objects.get(pk=options["actor_id"]))
            page = assess_ready_consistency_page(
                actor_id=actor.pk,
                findings_limit=options["limit"],
                work_limit=options["work_limit"],
                cursor=options["cursor"],
                check_physical=options["check_physical"],
            )
        except (User.DoesNotExist, ValueError, InventoryCursorError, InventoryWorkLimitError,
                ArtifactStorageError, DatabaseError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            f"ASSESSMENT: findings={len(page.issues)} work={page.work_performed} "
            f"complete={str(page.complete).lower()} physical={str(options['check_physical']).lower()}"
        )
        for issue in page.issues:
            self.stdout.write(f"{issue.kind} id={issue.identifier}")
        if page.next_cursor:
            self.stdout.write(f"CONTINUATION: {page.next_cursor}")
