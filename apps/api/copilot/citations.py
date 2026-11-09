import uuid
from dataclasses import dataclass


_CITATION_NAMESPACE = uuid.UUID("af52f3aa-429b-4c55-a929-72821840b7b0")


class InvalidCitation(Exception):
    pass


def citation_id_for(evidence):
    identity = f"{evidence.document_id}:{evidence.version_id}:{evidence.chunk_id}"
    return f"cite_{uuid.uuid5(_CITATION_NAMESPACE, identity).hex}"


def released_citations(evidence_items):
    citations = []
    seen = set()
    for evidence in evidence_items:
        citation_id = citation_id_for(evidence)
        if citation_id in seen:
            continue
        seen.add(citation_id)
        citations.append({
            "id": citation_id,
            "document_id": str(evidence.document_id),
            "version_id": str(evidence.version_id),
            "label": evidence.document_title,
            "version_sequence": evidence.version_sequence,
        })
    return tuple(citations)


def validate_citation_ids(requested_ids, available):
    available_by_id = {item["id"]: item for item in available}
    if not isinstance(requested_ids, (tuple, list)) or any(not isinstance(item, str) for item in requested_ids):
        raise InvalidCitation("Citation references are invalid")
    if len(requested_ids) != len(set(requested_ids)):
        raise InvalidCitation("Citation references are invalid")
    try:
        return tuple(available_by_id[item] for item in requested_ids)
    except KeyError as exc:
        raise InvalidCitation("Citation references are invalid") from exc
