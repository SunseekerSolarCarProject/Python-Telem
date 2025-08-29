"""
Bootstrap a brand-new TUF root and role keys.

This script:
- Generates fresh ED25519 keys for: root, targets, snapshot, timestamp
- Creates and signs a new src/updater/metadata/root.json with the new keys
- Exports decrypted private key JSON for CI secrets (targets/snapshot/timestamp)
- Prints the generated passwords (store securely!)

NOTES
- Losing the old root key means you cannot rotate — you must re-bootstrap.
- Keep the ROOT private key offline and NEVER put it in CI or the repo.

Prereqs
- pip install securesystemslib (installed transitively by tuf/tufup)

Usage
  python scripts/bootstrap_tuf_root.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import json
import secrets
import string
import sys
import getpass
from datetime import datetime, timedelta, timezone

try:
    from securesystemslib.interface import (
        generate_and_write_ed25519_keypair,
        import_ed25519_privatekey_from_file,
        import_publickeys_from_file,
    )
    from securesystemslib import KEY_TYPE_ED25519
    from securesystemslib.formats import encode_canonical
    from securesystemslib import keys as sslib_keys
except Exception as e:  # pragma: no cover
    print("Missing dependency: securesystemslib. Try: pip install securesystemslib", file=sys.stderr)
    raise


REPO_ROOT = Path(__file__).resolve().parents[1]
KEYS_DIR = REPO_ROOT / "src/updater/keys"
ROOT_JSON_PATH = REPO_ROOT / "src/updater/metadata/root.json"
EXPORT_DIR = REPO_ROOT / "scripts/exported_keys"


def _rand_password(length: int = 28) -> str:
    # URL-safe, copy/paste friendly: letters + digits + _-
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _write_role_key(role: str, password: str) -> Tuple[str, Dict]:
    """Generate a new ed25519 keypair for 'role' into KEYS_DIR/role,
    return (keyid, keymeta) where keymeta is the public key metadata dict.
    """
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    priv_path = KEYS_DIR / role
    # Overwrite any existing files for the role
    generate_and_write_ed25519_keypair(password=password, filepath=str(priv_path))
    pub_path = str(priv_path) + ".pub"
    # Force ED25519
    pub_map = import_publickeys_from_file([pub_path], key_types=[KEY_TYPE_ED25519])
    if len(pub_map) != 1:
        raise RuntimeError(f"Unexpected public key count in {pub_path}")
    keyid, keymeta = next(iter(pub_map.items()))
    # Match existing shape (drop optional field)
    keymeta = dict(keymeta)
    keymeta.pop("keyid_hash_algorithms", None)
    return keyid, keymeta


def _export_private_json(role: str, password: str) -> Path:
    """Decrypt the newly written private key and export its JSON to EXPORT_DIR.
    Returns the path to the exported file.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    priv = import_ed25519_privatekey_from_file(str(KEYS_DIR / role), password=password)
    out_path = EXPORT_DIR / f"{role}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(priv, f, indent=2)
    return out_path


def _iso_expires(days: int = 365) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    # RFC3339/ISO8601 Zulu time
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    print("BOOTSTRAP: Create new TUF root and role keys")
    print(f"Repo root: {REPO_ROOT}")
    print("This will OVERWRITE src/updater/keys/{root,targets,snapshot,timestamp} and root.json.")
    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
        return 1

    # Ask for a ROOT key password (or auto-generate if blank)
    root_pw = getpass.getpass("Set password for ROOT key (leave blank to auto-generate): ")
    if root_pw:
        root_pw2 = getpass.getpass("Re-enter ROOT password: ")
        if root_pw2 != root_pw:
            print("ERROR: Passwords did not match")
            return 1
    else:
        root_pw = _rand_password()
        print("Generated random ROOT password.")

    roles = ("targets", "snapshot", "timestamp")
    passwords: Dict[str, str] = {r: _rand_password() for r in roles}

    print("- Generating keys...")
    root_keyid, root_kmeta = _write_role_key("root", root_pw)
    print(f"  root      keyid: {root_keyid}")
    new_roles: Dict[str, Tuple[str, Dict]] = {}
    for role in roles:
        kid, meta = _write_role_key(role, passwords[role])
        new_roles[role] = (kid, meta)
        print(f"  {role:9s}keyid: {kid}")

    # Build 'signed' root metadata
    signed = {
        "_type": "root",
        "spec_version": "1.0.31",
        "consistent_snapshot": False,
        "version": 1,
        "expires": _iso_expires(365),  # rotate root at least yearly
        "keys": {},
        "roles": {
            "root": {"keyids": [root_keyid], "threshold": 1},
            "targets": {"keyids": [new_roles["targets"][0]], "threshold": 1},
            "snapshot": {"keyids": [new_roles["snapshot"][0]], "threshold": 1},
            "timestamp": {"keyids": [new_roles["timestamp"][0]], "threshold": 1},
        },
    }
    # Assemble keys map
    keys_map: Dict[str, Dict] = {root_keyid: root_kmeta}
    for role, (kid, kmeta) in new_roles.items():
        keys_map[kid] = kmeta
    signed["keys"] = keys_map

    # Sign with root private key
    print("- Signing new root.json with the new ROOT key...")
    root_priv = import_ed25519_privatekey_from_file(str(KEYS_DIR / "root"), password=root_pw)
    payload = encode_canonical(signed)
    # Some versions may return str; ensure bytes for PyNaCl
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    signature = sslib_keys.create_signature(root_priv, payload)

    root_all = {
        "signed": signed,
        "signatures": [{"keyid": signature["keyid"], "sig": signature["sig"]}],
    }

    # Ensure metadata dir
    ROOT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    ROOT_JSON_PATH.write_text(json.dumps(root_all, indent=1) + "\n", encoding="utf-8")
    print(f"- Wrote {ROOT_JSON_PATH}")

    # Export CI secrets for the three online roles
    print("- Exporting decrypted private keys for CI secrets...")
    exported: Dict[str, Path] = {}
    for role in roles:
        exported[role] = _export_private_json(role, passwords[role])
        print(f"  wrote {exported[role]}")

    # Final summary with passwords
    print("\nDONE. Store these passwords securely:")
    print(f"  root     : {root_pw}")
    for role in roles:
        print(f"  {role:9s}: {passwords[role]}")

    print("\nUpdate GitHub Secrets with the exported JSON:")
    print(f"  TUF_KEY_TARGETS_JSON   <- {exported['targets']}")
    print(f"  TUF_KEY_SNAPSHOT_JSON  <- {exported['snapshot']}")
    print(f"  TUF_KEY_TIMESTAMP_JSON <- {exported['timestamp']}")

    print("\nIMPORTANT:\n- Keep ROOT private key/password offline. Do NOT put root in CI.\n"
          "- The app bundles src/updater/metadata/root.json. Ship a new build so clients trust the new root.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
