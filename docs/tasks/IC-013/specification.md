# IC-013 Specification - Document Processing Worker and Text Extraction

**Feature:** F-03 Documentation Management
**Batch:** C
**Baseline:** `ea47fe4f0d6a4555cb9ac449654910afc61ae318`

## Contract

- `manage.py process_documents` is independently runnable with one-shot, bounded-count, and continuous polling modes. It exposes no inbound network endpoint.
- PDF uses strict pypdf extraction. TXT and Markdown use strict UTF-8 decoding; Markdown is inert text. Output normalizes CRLF/CR to LF and Unicode to NFC.
- Output is nonempty normalized UTF-8, limited to 2,000,000 characters, and records byte length, character count, SHA-256, extractor version, and PDF page count.
- Extraction cannot start until its child is assigned to the reviewed Windows Job Object. The job has kill-on-close, a 512 MiB aggregate memory ceiling, two-process ceiling, and a parent-enforced 120-second deadline.
- The child receives private input/output paths only through the post-containment stdin handshake. stderr is discarded; stdout is bounded safe metadata. Worker logs contain controlled outcome/count values only.
- Results are written under opaque, version-specific private keys inheriting the same ACL, containment, backup, retention, and non-public-serving boundary as originals.
- Publication transactionally revalidates the document, version, candidate pointer, cancellation state, lease owner, attempt, and expiry. Rejected or failed staging output is removed or privately quarantined.

Extraction does not chunk, embed, rank, retrieve, call external AI, or introduce F-04 behavior.
