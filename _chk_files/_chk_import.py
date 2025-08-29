from securesystemslib.interface import import_ed25519_privatekey_from_file
import json
from pathlib import Path
p = Path('src/updater/keys/root')
# Skip if not exists
if p.exists():
    try:
        key = import_ed25519_privatekey_from_file(str(p), password='x')
    except Exception as e:
        print('expected error loading with wrong password:', type(e).__name__)
