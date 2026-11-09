import re
from dataclasses import dataclass

from django.conf import settings
from django.db import connection
from django.db.models import Q

from accounts.models import User
from documents.policies import is_active_identity, visible_documents
from documents.retrieval import RetrievalCandidate, release_authorized_evidence

from .chunking import count_tokens
from .models import RetrievalChunk, RetrievalIndexGeneration


_WHITESPACE = re.compile(r"\s+")
_TERM = re.compile(r"\w+", re.UNICODE)


class InvalidQuestion(Exception):
    pass


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: object
    document_id: object
    version_id: object
    document_title: str
    version_sequence: int
    ordinal: int
    text: str
    token_count: int
    score: float


@dataclass(frozen=True)
class RetrievalResult:
    question: str
    evidence: tuple[EvidenceChunk, ...]
    insufficient_evidence: bool


def normalize_question(question):
    if not isinstance(question, str):
        raise InvalidQuestion("Question is invalid")
    normalized = _WHITESPACE.sub(" ", question).strip()
    if not normalized or len(normalized) > settings.COPILOT_QUESTION_MAX_CHARACTERS:
        raise InvalidQuestion("Question is invalid")
    return normalized


def _mysql_candidates(queryset, question, limit):
    expression = "MATCH(searchable_text) AGAINST (%s IN NATURAL LANGUAGE MODE)"
    return list(
        queryset.extra(
            select={"lexical_score": expression},
            where=[expression],
            params=[question],
            select_params=[question],
        ).order_by("-lexical_score", "id")[:limit]
    )


def _portable_candidates(queryset, question, limit):
    terms = tuple(dict.fromkeys(term.lower() for term in _TERM.findall(question)))
    if not terms:
        return []
    condition = Q()
    for term in terms:
        condition |= Q(searchable_text__icontains=term)
    rows = list(queryset.filter(condition).order_by("id")[:limit])
    for row in rows:
        lowered = row.searchable_text.lower()
        row.lexical_score = float(sum(lowered.count(term) for term in terms))
    return sorted(rows, key=lambda row: (-row.lexical_score, str(row.pk)))[:limit]


def retrieve_authorized_evidence(*, actor, question, store=None):
    question = normalize_question(question)
    actor_id = getattr(actor, "pk", None)
    fresh_actor = User.objects.filter(pk=actor_id).first() if actor_id else None
    if not is_active_identity(fresh_actor):
        return RetrievalResult(question, (), True)
    visible = visible_documents(fresh_actor, include_archived=False).values("pk")
    queryset = RetrievalChunk.objects.filter(
        generation__status=RetrievalIndexGeneration.Status.PUBLISHED,
        generation__searchable_slot=True,
        document_id__in=visible,
    ).select_related("generation")
    if connection.vendor == "mysql":
        rows = _mysql_candidates(queryset, question, settings.COPILOT_INDEX_CANDIDATE_LIMIT)
    else:
        rows = _portable_candidates(queryset, question, settings.COPILOT_INDEX_CANDIDATE_LIMIT)
    if not rows:
        return RetrievalResult(question, (), True)
    candidates = tuple(dict.fromkeys(
        RetrievalCandidate(row.document_id, row.document_version_id, row.generation.source_digest)
        for row in rows
    ))
    def materialize(authorized_candidates):
        authorized = {
            (item.document_id, item.version_id, item.digest): item
            for item in authorized_candidates
        }
        question_lower = question.lower()
        ranked = []
        for row in rows:
            key = (row.document_id, row.document_version_id, row.generation.source_digest)
            allowed = authorized.get(key)
            if allowed is None:
                continue
            score = float(row.lexical_score)
            if question_lower in row.searchable_text.lower():
                score += 2.0
            title_terms = set(_TERM.findall(allowed.title.lower()))
            score += 0.25 * len(title_terms.intersection(_TERM.findall(question_lower)))
            if score > 0:
                ranked.append((score, str(row.document_id), str(row.document_version_id), row.ordinal, str(row.pk), row, allowed))
        ranked.sort(key=lambda value: (-value[0], value[1], value[2], value[3], value[4]))
        evidence = []
        per_document = {}
        total_tokens = 0
        for score, _, _, _, _, row, allowed in ranked:
            used = per_document.get(row.document_id, 0)
            if used >= settings.COPILOT_EVIDENCE_PER_DOCUMENT_LIMIT:
                continue
            if total_tokens + row.token_count > settings.COPILOT_EVIDENCE_TOKEN_LIMIT:
                continue
            evidence.append(EvidenceChunk(
                row.pk, row.document_id, row.document_version_id, allowed.title,
                allowed.version_sequence, row.ordinal, row.searchable_text, row.token_count, score,
            ))
            per_document[row.document_id] = used + 1
            total_tokens += row.token_count
            if len(evidence) >= settings.COPILOT_EVIDENCE_CHUNK_LIMIT:
                break
        return RetrievalResult(question, tuple(evidence), not evidence)

    return release_authorized_evidence(
        actor=fresh_actor, candidates=candidates, materialize=materialize, store=store,
    )
