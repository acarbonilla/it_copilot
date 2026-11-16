from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate, dispatch_uid="vault.ensure_maintenance_guard")
def ensure_maintenance_guard(*, app_config, using, **kwargs):
    if app_config.label != "vault":
        return
    from .models import VaultMaintenanceGuard

    VaultMaintenanceGuard.objects.using(using).get_or_create(pk=1)
