from .models import ArtifactPublicationGuard, QuarantinedArtifact


class ArtifactPublicationRejected(Exception):
    pass


def lock_artifact_publication():
    """Acquire first in every artifact-reference publication/quarantine transaction."""
    return ArtifactPublicationGuard.objects.select_for_update().get(pk=1)


def reject_quarantined_key(storage_key):
    if QuarantinedArtifact.objects.filter(storage_key=storage_key).exists():
        raise ArtifactPublicationRejected("Artifact was quarantined before publication")
