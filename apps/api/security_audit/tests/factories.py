from itertools import count
from types import SimpleNamespace

from accounts.models import User


_user_sequence = count(1)


def user_factory(*, password="factory-password", **overrides):
    sequence = next(_user_sequence)
    fields = {
        "email": f"audit-user-{sequence}@example.test",
        "it_role": User.ITRole.NONE,
        "is_active": True,
        "is_app_admin": False,
    }
    fields.update(overrides)
    email = fields.pop("email")
    return User.objects.create_user(email, password, **fields)


def subject_factory(*, pk=1, it_role=User.ITRole.NONE, is_active=True, is_app_admin=False, **overrides):
    fields = {
        "pk": pk,
        "it_role": it_role,
        "is_active": is_active,
        "is_app_admin": is_app_admin,
        "is_staff": False,
        "is_superuser": False,
        "is_authenticated": True,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)
