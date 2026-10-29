from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate, dispatch_uid="accounts.ensure_admin_lifecycle_guard")
def ensure_admin_lifecycle_guard(*, app_config, **kwargs):
    if app_config.label != "accounts":
        return
    from .models import AdminLifecycleGuard

    AdminLifecycleGuard.objects.get_or_create(pk=1)
