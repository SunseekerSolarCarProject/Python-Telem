"""
Rotate TUF role keys (targets, snapshot, timestamp) with fresh passwords,
update and re-sign root metadata, export decrypted key JSON for CI secrets,
and print the new passwords at the end.

Prereqs:
- You have Python deps installed: securesystemslib (and tuf if you want to
  validate), but this script only uses securesystemslib.
- You know the root key password (to re-sign root.json). Root key files live
  in src/updater/keys/root and src/updater/keys/root.pub.

Outputs:
- Overwrites src/updater/keys/{targets,snapshot,timestamp} (+ .pub)
- Updates src/updater/metadata/root.json with the new keyids
- Writes decrypted private key JSON to scripts/exported_keys/{role}.json
- Prints the three generated passwords so you can save them safely

NOTE: After running, update your GitHub repository secrets:
  - TUF_KEY_TARGETS_JSON   -> contents of scripts/exported_keys/targets.json
  - TUF_KEY_SNAPSHOT_JSON  -> contents of scripts/exported_keys/snapshot.json
  - TUF_KEY_TIMESTAMP_JSON -> contents of scripts/exported_keys/timestamp.json

Usage:
  python scripts/rotate_tuf_keys.py
"""

from __future__ import annotations

from pathlib import Path
import json
import secrets
import string
import sys
import getpass
from typing import Dict, Tuple

from securesystemslib.interface import (
    generate_and_write_ed25519_keypair,
    import_ed25519_privatekey_from_file,
    import_publickeys_from_file,
)
from securesystemslib import KEY_TYPE_ED25519
from securesystemslib.formats import encode_canonical
from securesystemslib import keys as sslib_keys


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
    # The interface defaults to RSA unless we specify key_types; force ED25519.
    pub_map = import_publickeys_from_file([pub_path], key_types=[KEY_TYPE_ED25519])  # {keyid: keymeta}
    if len(pub_map) != 1:
        raise RuntimeError(f"Unexpected public key count in {pub_path}")
    keyid, keymeta = next(iter(pub_map.items()))
    # Sanitize to match existing root.json shape (drop optional field)
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


def _update_root_signed(signed: Dict, new_roles: Dict[str, Tuple[str, Dict]]) -> Dict:
    """Return updated 'signed' (dict) with new keyids for the 3 roles.
    new_roles: {'targets': (keyid, keymeta), ...}
    - bumps version by +1
    - updates 'keys' map and 'roles' keyids
    - prunes keys not referenced by any role
    """
    keys_map = signed.get("keys") or {}
    roles_map = signed.get("roles") or {}

    # Replace role keyids and add key meta
    for role, (kid, kmeta) in new_roles.items():
        # Add/replace key metadata under new keyid
        keys_map[kid] = kmeta
        # Set the role to reference only the new keyid
        if role not in roles_map:
            raise RuntimeError(f"root.json missing role entry for '{role}'")
        roles_map[role]["keyids"] = [kid]

    # Compute the set of referenced keyids after replacement
    referenced: set[str] = set()
    for role, rinfo in roles_map.items():
        for kid in rinfo.get("keyids", []):
            referenced.add(kid)

    # Prune any keys not referenced by a role
    keys_map = {kid: k for kid, k in keys_map.items() if kid in referenced}

    # Bump version
    try:
        signed["version"] = int(signed.get("version", 1)) + 1
    except Exception:
        signed["version"] = 2

    signed["keys"] = keys_map
    signed["roles"] = roles_map
    return signed


def main() -> int:
    print("TUF key rotation: targets/snapshot/timestamp")
    print(f"Repo root: {REPO_ROOT}")
    if not ROOT_JSON_PATH.exists():
        print(f"ERROR: Missing {ROOT_JSON_PATH}")
        return 1

    confirm = input(
        "This will OVERWRITE src/updater/keys/{targets,snapshot,timestamp}. Proceed? [y/N]: "
    ).strip().lower()
    if confirm not in ("y", "yes"):  # abort unless explicitly yes
        print("Aborted.")
        return 1

    # 1) Create new keys with random passwords
    roles = ("targets", "snapshot", "timestamp")
    passwords: Dict[str, str] = {r: _rand_password() for r in roles}
    new_roles: Dict[str, Tuple[str, Dict]] = {}
    for role in roles:
        print(f"- Generating {role} key...")
        kid, kmeta = _write_role_key(role, passwords[role])
        print(f"  keyid: {kid}")
        new_roles[role] = (kid, kmeta)

    # 2) Update root.json 'signed' block
    root_all = json.loads(ROOT_JSON_PATH.read_text(encoding="utf-8"))
    signed = root_all.get("signed")
    if not isinstance(signed, dict):
        print("ERROR: root.json missing 'signed' object")
        return 1

    signed = _update_root_signed(signed, new_roles)

    # 3) Sign the updated 'signed' with root private key
    print("- Signing updated root.json with root key...")
    try:
        root_pw = getpass.getpass("Password for src/updater/keys/root: ")
        root_priv = import_ed25519_privatekey_from_file(str(KEYS_DIR / "root"), password=root_pw)
    except Exception as e:
        print(f"ERROR: Could not import root private key: {e}")
        print("If you've also lost the root password, you'll need to bootstrap a new root.json.")
        return 1

    payload = encode_canonical(signed)
    # Ensure payload is bytes for PyNaCl signer
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    signature = sslib_keys.create_signature(root_priv, payload)
    root_all["signed"] = signed
    root_all["signatures"] = [
        {"keyid": signature["keyid"], "sig": signature["sig"]}
    ]

    # 4) Write root.json
    ROOT_JSON_PATH.write_text(json.dumps(root_all, indent=1) + "\n", encoding="utf-8")
    print(f"- Updated {ROOT_JSON_PATH}")

    # 5) Export decrypted private key JSON for CI secrets
    print("- Exporting decrypted private keys for CI secrets...")
    exported: Dict[str, Path] = {}
    for role in roles:
        outp = _export_private_json(role, passwords[role])
        exported[role] = outp
        print(f"  wrote {outp}")

    # 6) Final summary with passwords
    print("\nDONE. Store these passwords securely:")
    for role in roles:
        print(f"  {role:9s}: {passwords[role]}")

    print("\nUpdate GitHub Secrets with the exported JSON:")
    print(f"  TUF_KEY_TARGETS_JSON   <- {exported['targets']}")
    print(f"  TUF_KEY_SNAPSHOT_JSON  <- {exported['snapshot']}")
    print(f"  TUF_KEY_TIMESTAMP_JSON <- {exported['timestamp']}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
