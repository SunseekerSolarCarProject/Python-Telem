"""
Prepare signing keys for CI:

- Prefer GitHub Secrets env vars:
    TUF_KEY_TARGETS_JSON_B64 / TUF_KEY_TARGETS_JSON
    TUF_KEY_SNAPSHOT_JSON_B64 / TUF_KEY_SNAPSHOT_JSON
    TUF_KEY_TIMESTAMP_JSON_B64 / TUF_KEY_TIMESTAMP_JSON

- Fallback: copy decrypted private key JSON from a directory
  (default: scripts/exported_keys) into the keys dir.

Writes to: src/updater/keys/{targets,snapshot,timestamp}

Exits non-zero on any error. Prints concise diagnostics.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path


ROLES = ("targets", "snapshot", "timestamp")


def _is_key_json(obj) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("keyval"), dict) and {
        "public",
        "private",
    }.issubset(obj["keyval"].keys())


def _load_from_env(role: str) -> str | None:
    upper = role.upper()
    b64 = os.environ.get(f"TUF_KEY_{upper}_JSON_B64")
    raw = os.environ.get(f"TUF_KEY_{upper}_JSON")
    if b64:
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception as e:
            print(f"ERROR: could not base64-decode TUF_KEY_{upper}_JSON_B64: {e}")
            return None
    if raw:
        return raw
    return None


def _load_from_dir(role: str, src_dir: Path) -> str | None:
    cand = src_dir / f"{role}.json"
    if cand.exists():
        return cand.read_text(encoding="utf-8")
    return None


def _write_key(content: str, dest: Path) -> bool:
    try:
        data = json.loads(content)
    except Exception as e:
        print(f"ERROR: JSON parse failed for {dest.name}: {e}")
        return False
    if not _is_key_json(data):
        if isinstance(data, dict) and "signed" in data:
            print(
                f"ERROR: {dest.name}: JSON looks like TUF metadata (has 'signed'); expected private key JSON."
            )
        else:
            print(
                f"ERROR: {dest.name}: JSON does not have keyval.private/keyval.public; not a private key JSON."
            )
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(dest, 0o600)
    except Exception:
        pass
    print(f"Wrote {dest}")
    return True


def main(argv: list[str]) -> int:
    # Simple argv parsing: --from-dir DIR, --keys-dir DIR
    from_dir = None
    keys_dir = Path("src/updater/keys")
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg == "--from-dir" and i + 1 < len(argv):
            from_dir = Path(argv[i + 1])
            i += 2
            continue
        if arg == "--keys-dir" and i + 1 < len(argv):
            keys_dir = Path(argv[i + 1])
            i += 2
            continue
        print(f"Unknown argument: {arg}")
        return 2

    # Default fallback directory
    if from_dir is None:
        from_dir = Path("scripts/exported_keys")

    ok = True
    for role in ROLES:
        content = _load_from_env(role)
        src_note = "env"
        if not content:
            content = _load_from_dir(role, from_dir)
            src_note = str(from_dir)
        if not content:
            print(
                f"ERROR: Missing {role} key in env and no fallback file at {from_dir}/{role}.json"
            )
            ok = False
            continue
        dest = keys_dir / role
        print(f"Preparing {role} key from {src_note} -> {dest}")
        if not _write_key(content, dest):
            ok = False

    if not ok:
        return 1

    # Final validation (reuse validator script if available)
    try:
        from validate_keys_json import validate_paths as _validate

        rc = _validate([str(keys_dir / r) for r in ROLES])
        if rc != 0:
            return rc
    except Exception:
        # Fall back to simple load
        for role in ROLES:
            json.loads((keys_dir / role).read_text(encoding="utf-8"))

    print("Keys prepared and validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

