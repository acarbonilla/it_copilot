"""Untrusted request material for transaction-bound vault authorization."""

from dataclasses import dataclass

@dataclass(frozen=True)
class SensitiveAuthorization:
    """Carries a bounded proof and exact session key; it grants no authority itself."""

    proof: str
    session_key: str
