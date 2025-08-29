# scripts/export_tuf_keys.py
from pathlib import Path
import json, getpass, sys
from securesystemslib.interface import import_ed25519_privatekey_from_file

# Where your encrypted key files live:
KEYS_DIR = Path("src/updater/keys")

# Where to write the decrypted JSON (gitignored recommended)
OUT_DIR = Path("scripts/exported_keys")

def export_one(name: str, pw_cache: dict):
    src = KEYS_DIR / name
    if not src.exists():
        print(f"ERROR: missing {src}", file=sys.stderr)
        return False
    pw = getpass.getpass(f"Password for '{src}': ")
    pw_cache[name] = pw
    key = import_ed25519_privatekey_from_file(str(src), password=pw)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{name}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(key, f, indent=2)
    print(f"Wrote {out_path}")
    return True

ok = True
passwords = {}
for name in ("targets", "snapshot", "timestamp"):
    ok &= export_one(name, passwords)

if not ok:
    sys.exit(1)

print(
    "\nDone. Open the three files under scripts/exported_keys "
    "and copy their FULL JSON (including braces) into GitHub Secrets:\n"
    "  - TUF_KEY_TARGETS_JSON   -> targets.json\n"
    "  - TUF_KEY_SNAPSHOT_JSON  -> snapshot.json\n"
    "  - TUF_KEY_TIMESTAMP_JSON -> timestamp.json\n"
)

print("\nPasswords you entered (store securely):")
for name in ("targets", "snapshot", "timestamp"):
    print(f"  {name:9s}: {passwords.get(name, '')}")
