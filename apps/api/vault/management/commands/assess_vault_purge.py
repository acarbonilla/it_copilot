from django.core.management.base import BaseCommand, CommandError

from vault.maintenance import MaintenanceAuthorizationDenied, authenticate_maintenance_operator
from vault.maintenance_services import MaintenanceStateError, assess_purge, audit_maintenance_denial


class Command(BaseCommand):
    help = "Create a bounded read-only vault purge assessment. This command cannot purge credentials."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", required=True)
        parser.add_argument("--token-file", required=True)
        parser.add_argument("--owner-id", type=int)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--execute", action="store_true", help="Unsupported fail-closed option")

    def handle(self, *args, **options):
        if options["execute"]:
            raise CommandError("Execution is not available in IC-023-T02A")
        try:
            principal = authenticate_maintenance_operator(
                operator_id=options["operator_id"], token_file=options["token_file"],
                required_capability="credential.purge",
            )
            operation = assess_purge(
                principal=principal, owner_id=options["owner_id"], limit=options["limit"])
        except (MaintenanceAuthorizationDenied, MaintenanceStateError, ValueError) as exc:
            audit_maintenance_denial()
            raise CommandError("Vault purge assessment denied") from exc
        self.stdout.write(
            f"ASSESSMENT operation={operation.pk} eligible={operation.eligible_count} "
            f"blocked={operation.blocked_count} destructive=false"
        )
