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
    repo = Repository(app_name=app_name, repo_dir=repo_dir)
    repo.save_config()   # writes repo/config.json if needed
    # Avoid interactive key creation/overwrite prompts in CI. We load root.json
    # ourselves and provide signing keys via repo.publish_changes([keys_dir]).
    try:
        repo.initialize(create_keys=False)  # tufup>=0.19 supports this kwarg
    except TypeError:
        # Fallback for older tufup: still call initialize(), but note this may
        # try to create keys if none exist. In CI we ensure keys are provided.
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
