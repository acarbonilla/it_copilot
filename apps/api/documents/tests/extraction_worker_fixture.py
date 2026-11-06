import json
import os
import sys
import time


def main():
    request = json.loads(sys.stdin.buffer.readline(8192).decode("utf-8"))
    mode = os.environ.get("DOCUMENT_EXTRACTION_FIXTURE", "success")
    if mode == "timeout":
        time.sleep(30)
    if mode == "memory":
        blocks = []
        try:
            while True:
                blocks.append(bytearray(1024 * 1024))
        except MemoryError:
            print('{"ok":false,"code":"resource_limit"}', end="")
            return 3
    if mode == "failure":
        return 7
    data = b"fixture\n"
    with open(request["output_path"], "xb") as output:
        output.write(data)
    print(
        json.dumps(
            {
                "ok": True,
                "characters": 8,
                "bytes": 8,
                "digest": "70a669453f561a1bf59eab8e5bd642840d24506f77e7ca4b71243a285e02a990",
                "pages": None,
                "extractor": "fixture-v1",
            },
            separators=(",", ":"),
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
