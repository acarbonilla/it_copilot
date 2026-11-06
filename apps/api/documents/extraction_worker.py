import hashlib
import json
import os
import sys
import unicodedata


MAX_CHARACTERS = 2_000_000
EXTRACTOR_VERSION = "local-text-v1"


def _response(ok, **values):
    sys.stdout.write(json.dumps({"ok": ok, **values}, separators=(",", ":")))
    sys.stdout.flush()


def _normalize(parts):
    text = unicodedata.normalize("NFC", "".join(parts).replace("\r\n", "\n").replace("\r", "\n"))
    if len(text) > MAX_CHARACTERS:
        raise ValueError("character_limit")
    return text


def _extract_pdf(path):
    from pypdf import PdfReader

    try:
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            raise ValueError("invalid")
        parts = []
        count = 0
        for page in reader.pages:
            value = page.extract_text() or ""
            count += len(value)
            if count > MAX_CHARACTERS:
                raise ValueError("character_limit")
            parts.append(value)
            parts.append("\n")
        return _normalize(parts), len(reader.pages)
    except (MemoryError, ValueError):
        raise
    except Exception as exc:
        raise ValueError("invalid") from exc


def _extract_text(path):
    with open(path, "rb") as source:
        data = source.read()
    return _normalize([data.decode("utf-8", errors="strict")]), None


def main():
    # Parsing cannot begin until the parent assigns the child to its Job Object
    # and sends this private-path handshake.
    try:
        request = json.loads(sys.stdin.buffer.readline(8192).decode("utf-8"))
        input_path = request["input_path"]
        output_path = request["output_path"]
        media_type = request["media_type"]
    except Exception:
        return 4
    try:
        if media_type == "application/pdf":
            text, pages = _extract_pdf(input_path)
        elif media_type in {"text/plain", "text/markdown"}:
            text, pages = _extract_text(input_path)
        else:
            raise ValueError("unsupported")
        encoded = text.encode("utf-8")
        if not encoded:
            raise ValueError("empty")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(output_path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        _response(
            True,
            characters=len(text),
            bytes=len(encoded),
            digest=hashlib.sha256(encoded).hexdigest(),
            pages=pages,
            extractor=EXTRACTOR_VERSION,
        )
        return 0
    except MemoryError:
        _response(False, code="resource_limit")
        return 3
    except ValueError as exc:
        _response(False, code=str(exc) if str(exc) in {"character_limit", "unsupported"} else "invalid")
        return 2
    except (UnicodeDecodeError, OSError):
        _response(False, code="invalid")
        return 2
    except Exception:
        _response(False, code="parser_failure")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
