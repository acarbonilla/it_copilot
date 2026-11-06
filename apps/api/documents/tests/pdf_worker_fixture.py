import json
import os
import sys
import time


def main():
    if not sys.stdin.buffer.readline(4096):
        return 9
    mode = os.environ.get("DOCUMENT_PDF_FIXTURE_MODE")
    if mode == "timeout":
        time.sleep(60)
        return 0
    if mode == "memory":
        allocations = []
        try:
            while True:
                allocations.append(bytearray(1024 * 1024))
        except MemoryError:
            sys.stdout.write(json.dumps({"ok": False, "code": "resource_limit"}))
            return 3
    if mode == "failure":
        return 7
    sys.stdout.write(json.dumps({"ok": True, "pages": 1}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
