from django.core.management.base import BaseCommand, CommandError

from copilot.conversations import purge_expired_conversations


class Command(BaseCommand):
    help = "Report or delete a bounded batch of expired Copilot conversations."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        try:
            ids = purge_expired_conversations(limit=options["limit"], execute=options["execute"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        mode = "deleted" if options["execute"] else "dry_run"
        self.stdout.write(f"mode={mode} count={len(ids)}")
