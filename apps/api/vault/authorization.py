"""Production authorization boundary for IC-021.

IC-022 will replace this fail-closed placeholder with grant validation.
No test credential or test-mode switch is accepted here.
"""

class SensitiveAuthorization:
    """Non-instantiable placeholder for the future grant authorization."""

    def __new__(cls, *args, **kwargs):
        raise PermissionError("Sensitive vault authorization is unavailable")

    def valid_for(self, actor_id):
        return False
