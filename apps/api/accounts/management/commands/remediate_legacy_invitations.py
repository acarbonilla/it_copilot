from django.core.management.base import BaseCommand, CommandError

from accounts.legacy_invitation_remediation import (
    legacy_candidate_ids,
    remediate_legacy_invitation,
    validate_remediation_actor,
)
from accounts.models import User


class Command(BaseCommand):
    help = "Revoke legacy path invitations and safely reissue eligible invitations (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--actor-id", type=int, required=True, help="Active, activated App Admin audit actor ID")
        parser.add_argument("--execute", action="store_true", help="Apply the remediation; omission is a dry run")

    def handle(self, *args, **options):
        try:
            actor = User.objects.get(pk=options["actor_id"])
            validate_remediation_actor(actor)
        except (User.DoesNotExist, ValueError) as exc:
            raise CommandError("Audit actor must identify an active, activated App Admin") from exc

        candidate_ids = legacy_candidate_ids()
        if not options["execute"]:
            self.stdout.write(f"DRY RUN: {len(candidate_ids)} legacy invitation(s) would be processed; no changes made.")
            return

        counts = {"reissued": 0, "revoked_without_reissue": 0, "already_remediated": 0}
        for invitation_id in candidate_ids:
            result = remediate_legacy_invitation(actor=actor, invitation_id=invitation_id)
            counts[result.outcome] += 1
            self.stdout.write(f"{result.invitation_id}: {result.outcome}")
        self.stdout.write(
            self.style.SUCCESS(
                "Completed: "
                f"{counts['reissued']} reissued, "
                f"{counts['revoked_without_reissue']} revoked without reissue, "
                f"{counts['already_remediated']} already remediated."
            )
        )
