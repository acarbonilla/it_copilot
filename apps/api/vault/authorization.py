from dataclasses import dataclass


_TEST_SEAM_TOKEN = object()


@dataclass(frozen=True)
class SensitiveAuthorization:
    actor_id: int
    _token: object

    def valid_for(self, actor_id):
        return self._token is _TEST_SEAM_TOKEN and self.actor_id == actor_id


def _issue_test_authorization(actor_id):
    """Private constructor used only by vault.testing; never imported by routes."""
    return SensitiveAuthorization(actor_id=actor_id, _token=_TEST_SEAM_TOKEN)
