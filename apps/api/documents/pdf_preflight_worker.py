import json
import sys


def _reject(code="invalid"):
    sys.stdout.write(json.dumps({"ok": False, "code": code}, separators=(",", ":")))
    sys.stdout.flush()
    return 2 if code == "invalid" else 3


def main():
    # Do not import or invoke the parser until the parent has assigned this
    # process to the constrained Windows Job Object and sends the handshake.
    payload = sys.stdin.buffer.readline(4096)
    try:
        path = json.loads(payload.decode("utf-8"))["path"]
    except Exception:
        return 4

    try:
        from pypdf import PdfReader

        with open(path, "rb") as source:
            if source.read(5) != b"%PDF-":
                return _reject()
            source.seek(0)
            reader = PdfReader(source, strict=True)
            if reader.is_encrypted:
                return _reject()
            page_count = len(reader.pages)
            root = reader.trailer.get("/Root")
            if root:
                root = root.get_object()
                if any(key in root for key in ("/OpenAction", "/AA")):
                    return _reject()
                names = root.get("/Names")
                if names:
                    names = names.get_object()
                    if any(key in names for key in ("/JavaScript", "/EmbeddedFiles")):
                        return _reject()
            for page in reader.pages:
                if any(key in page for key in ("/AA", "/OpenAction")):
                    return _reject()
                for annotation in page.get("/Annots") or ():
                    annotation = annotation.get_object()
                    if annotation.get("/Subtype") in {"/FileAttachment", "/RichMedia"}:
                        return _reject()
                    action = annotation.get("/A")
                    if action and action.get_object().get("/S") in {
                        "/JavaScript",
                        "/Launch",
                        "/SubmitForm",
                        "/ImportData",
                    }:
                        return _reject()
    except MemoryError:
        return _reject("resource_limit")
    except Exception:
        return _reject()

    sys.stdout.write(json.dumps({"ok": True, "pages": page_count}, separators=(",", ":")))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
