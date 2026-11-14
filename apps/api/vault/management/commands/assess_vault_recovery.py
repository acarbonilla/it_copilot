from django.core.management.base import BaseCommand, CommandError

from vault.maintenance import MaintenanceAuthorizationDenied, authenticate_maintenance_operator
from vault.maintenance_services import audit_maintenance_denial


class Command(BaseCommand):
    help = "Validate authorization for future recovery verification. No backup or key material is opened."

    def add_arguments(self, parser):
        parser.add_argument("--operator-id", required=True)
        parser.add_argument("--token-file", required=True)
        parser.add_argument("--execute", action="store_true", help="Unsupported fail-closed option")

    def handle(self, *args, **options):
        if options["execute"]:
            raise CommandError("Execution is not available in IC-023-T02A")
        try:
            principal = authenticate_maintenance_operator(
                operator_id=options["operator_id"], token_file=options["token_file"],
                required_capability="recovery.verify",
            )
        except MaintenanceAuthorizationDenied as exc:
            audit_maintenance_denial()
            raise CommandError("Vault recovery assessment denied") from exc
        self.stdout.write(f"ASSESSMENT operator={principal.operator_id} destructive=false")
