import hashlib
import re
from dataclasses import dataclass


TOKENIZER_VERSION = "unicode-regex-v1"
CHUNKER_VERSION = "paragraph-window-v1"
_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n", re.UNICODE)


@dataclass(frozen=True)
class Chunk:
    ordinal: int
    text: str
    digest: str
    token_count: int
    character_count: int


def token_spans(text):
    if not isinstance(text, str):
        raise TypeError("Chunk input must be text")
    return tuple((match.start(), match.end()) for match in _TOKEN.finditer(text))


def count_tokens(text):
    return len(token_spans(text))


def _paragraph_token_boundaries(text, spans):
    boundaries = set()
    for match in _PARAGRAPH_BREAK.finditer(text):
        for index, (start, _) in enumerate(spans):
            if start >= match.end():
                boundaries.add(index)
                break
    return boundaries


def chunk_text(text, *, max_tokens=600, overlap_tokens=80):
    if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
        raise ValueError("Chunk token limit is invalid")
    if (
        isinstance(overlap_tokens, bool) or not isinstance(overlap_tokens, int)
        or overlap_tokens < 0 or overlap_tokens >= max_tokens
    ):
        raise ValueError("Chunk overlap is invalid")
    spans = token_spans(text)
    if not spans:
        return ()
    paragraph_boundaries = _paragraph_token_boundaries(text, spans)
    chunks = []
    start = 0
    minimum_boundary = max(1, max_tokens // 2)
    while start < len(spans):
        hard_end = min(start + max_tokens, len(spans))
        end = hard_end
        if hard_end < len(spans):
            eligible = [
                boundary for boundary in paragraph_boundaries
                if start + minimum_boundary <= boundary <= hard_end
            ]
            if eligible:
                end = max(eligible)
        start_character = spans[start][0]
        end_character = spans[end - 1][1]
        value = text[start_character:end_character].strip()
        if value:
            encoded = value.encode("utf-8")
            chunks.append(Chunk(
                ordinal=len(chunks),
                text=value,
                digest=hashlib.sha256(encoded).hexdigest(),
                token_count=end - start,
                character_count=len(value),
            ))
        if end >= len(spans):
            break
        next_start = end - overlap_tokens
        if next_start <= start:
            next_start = start + 1
        start = next_start
    return tuple(chunks)
