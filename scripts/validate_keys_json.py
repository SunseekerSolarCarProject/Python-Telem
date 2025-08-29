import json
import sys
from pathlib import Path


def validate_paths(paths: list[str]) -> int:
    ok = True
    for p in paths:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                json.load(f)
        except Exception as e:
            # Try to give a helpful hint without leaking secrets
            try:
                with open(p, 'rb') as bf:
                    head = bf.read(200)
            except Exception:
                head = b''

            hint = ''
            if b'@@@@' in head:
                hint = ' (looks like an ENCRYPTED key file; use scripts/exported_keys/*.json instead)'
            elif b'keytype: ed25519' in head or b'scheme: ed25519' in head:
                hint = ' (looks like YAML-like text; you must paste exact JSON with double quotes)'
            elif head and not head.lstrip().startswith(b'{'):
                hint = ' (does not start with {; ensure you pasted the full JSON)'
            print(f"ERROR: {p} is not valid JSON: {e}{hint}")
            ok = False
        else:
            print(f"{p}: OK")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        paths = argv[1:]
    else:
        # Default locations used by the workflow
        paths = [
            'src/updater/keys/targets',
            'src/updater/keys/snapshot',
            'src/updater/keys/timestamp',
        ]

    # Normalize paths for readable output, but keep given order
    norm = [str(Path(p)) for p in paths]
    rc = validate_paths(norm)
    if rc == 0:
        print('All keys JSON parse OK')
    return rc


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))

