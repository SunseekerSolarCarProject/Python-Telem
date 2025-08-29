# scripts/build_tuf_repo.py
from pathlib import Path
from tufup.repo import Repository
import os
import sys

# VERSION comes from the workflow step that calls this script:
#   env TAG=v1.7.0 → VERSION=1.7.0 (stripped in the YAML step)
version = os.environ.get("VERSION") or os.environ.get("TAG", "").lstrip("v")
if not version:
    print("ERROR: VERSION env var is empty", file=sys.stderr)
    sys.exit(1)

repo_dir    = Path("release")
meta_dir    = repo_dir / "metadata"
targets_dir = repo_dir / "targets"
keys_dir    = Path("src/updater/keys")

# Ensure dirs & bootstrap trusted root
meta_dir.mkdir(parents=True, exist_ok=True)
targets_dir.mkdir(parents=True, exist_ok=True)
root_src = Path("src/updater/metadata/root.json")
if not root_src.exists():
    print("Missing src/updater/metadata/root.json", file=sys.stderr)
    sys.exit(1)
(meta_dir / "root.json").write_bytes(root_src.read_bytes())

def add_platform(app_name: str, bundle_dir: str, platform_tag: str):
    # app_name must match what clients expect (telemetry-windows/macos/linux)
    repo = Repository(app_name=app_name, repo_dir=repo_dir, keys_dir=repo_dir / 'keystore')
    repo.save_config()   # writes repo/config.json if needed
    # Manually perform a non-interactive init compatible with older tufup:
    # - ensure dirs exist
    # - load keys/roles WITHOUT creating/overwriting keys (avoid prompts)
    for p in [repo.keys_dir, repo.metadata_dir, repo.targets_dir]:
        p.mkdir(parents=True, exist_ok=True)
    # Older tufup exposes a private helper with this behavior
    if hasattr(repo, '_load_keys_and_roles'):
        repo._load_keys_and_roles(create_keys=False)  # type: ignore[attr-defined]
    else:
        # As a last resort, call initialize but ensure keystore is empty to avoid prompts
        # (should not happen with known tufup versions)
        try:
            import shutil
            if repo.keys_dir.exists():
                shutil.rmtree(repo.keys_dir)
        except Exception:
            pass
        repo.initialize()
    # Add the "bundle" folder; tufup creates telemetry-<platform>-<ver>.tar.gz
    repo.add_bundle(bundle_dir, new_version=version, skip_patch=True,
                    custom_metadata={"platform": platform_tag})
    # Sign targets/snapshot/timestamp with your keys, write metadata
    repo.publish_changes([keys_dir])

add_platform("telemetry-windows", "bundles/windows", "windows")
add_platform("telemetry-macos",   "bundles/macos",   "macos")
add_platform("telemetry-linux",   "bundles/linux",   "linux")
print("TUF repo built. Metadata and targets in ./release")
