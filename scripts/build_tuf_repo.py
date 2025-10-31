# scripts/build_tuf_repo.py
from pathlib import Path
from tufup.repo import Repository
import os
import re
import sys
from packaging.version import Version as SemVer


def _extract_version(raw: str) -> str | None:
    """
    Extract semver-like version from a tag/string.
    Accepts: 'v1.7.0', 'v.1.7.0', '1.7.0', 'v1.7.0-rc1', etc.
    Returns version only, e.g. '1.7.0' or '1.7.0-rc1'.
    """
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^[vV][._-]?", "", raw)
    m = re.match(r"^(\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z]+)*)$", raw)
    return m.group(1) if m else None


# VERSION comes from the workflow step; if absent sanitize TAG
raw = os.environ.get("VERSION") or os.environ.get("TAG", "")
version = _extract_version(raw)
if not version:
    print(f"ERROR: Could not parse VERSION from '{raw}'. Use tag like v1.7.0", file=sys.stderr)
    sys.exit(1)

repo_dir = Path("release")
meta_dir = repo_dir / "metadata"
targets_dir = repo_dir / "targets"
keys_dir = Path("src/updater/keys")

# Ensure dirs & bootstrap trusted root
meta_dir.mkdir(parents=True, exist_ok=True)
targets_dir.mkdir(parents=True, exist_ok=True)
root_src = Path("src/updater/metadata/root.json")
if not root_src.exists():
    print("Missing src/updater/metadata/root.json", file=sys.stderr)
    sys.exit(1)
(meta_dir / "root.json").write_bytes(root_src.read_bytes())


EXPIRATION_DAYS = {
    "root": 365,
    "targets": 60,
    "snapshot": 60,
    "timestamp": 60,
}


def _version_counter(ver: str) -> int:
    """
    Convert SemanticVersion to a monotonically increasing integer so metadata
    versions strictly increase across releases. Uses major/minor/micro along
    with pre/dev tags to maintain ordering.
    """
    v = SemVer(ver)
    # Multiply major/minor/micro into separate buckets to avoid collisions.
    counter = (v.major * 10**8) + (v.minor * 10**4) + v.micro
    # Incorporate pre/dev/post segments so beta/rc sort before final release.
    if v.pre:
        label, number = v.pre
        offset = {"a": 1, "alpha": 1, "b": 2, "beta": 2, "rc": 3}.get(label, 0)
        counter = counter * 10 + offset
        counter = counter * 10 + (number or 0)
    elif v.dev:
        counter = counter * 10 + 4
        counter = counter * 10 + (v.dev or 0)
    else:
        counter = counter * 100
    return counter


def add_platform(app_name: str, bundle_dir: str, platform_tag: str):
    # app_name must match what clients expect (telemetry-windows/macos/linux)
    repo = Repository(
        app_name=app_name,
        repo_dir=repo_dir,
        keys_dir=repo_dir / "keystore",
        expiration_days=EXPIRATION_DAYS,
    )
    repo.save_config()  # writes repo/config.json if needed
    # Manually perform a non-interactive init compatible with older tufup:
    # - ensure dirs exist
    # - load keys/roles WITHOUT creating/overwriting keys (avoid prompts)
    for p in [repo.keys_dir, repo.metadata_dir, repo.targets_dir]:
        p.mkdir(parents=True, exist_ok=True)
    # Older tufup exposes a private helper with this behavior
    if hasattr(repo, "_load_keys_and_roles"):
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
    repo.add_bundle(
        bundle_dir,
        new_version=version,
        skip_patch=True,
        custom_metadata={"platform": platform_tag},
    )
    version_counter = _version_counter(version)
    repo.roles.targets.signed.version = version_counter
    repo.roles.snapshot.signed.version = version_counter
    repo.roles.timestamp.signed.version = version_counter
    repo.roles.snapshot.signed.meta["targets.json"].version = version_counter
    repo.roles.timestamp.signed.snapshot_meta.version = version_counter
    # Sign targets/snapshot/timestamp with your keys, write metadata
    repo.publish_changes([keys_dir])


add_platform("telemetry-windows", "bundles/windows", "windows")
add_platform("telemetry-macos", "bundles/macos", "macos")
add_platform("telemetry-linux", "bundles/linux", "linux")
print("TUF repo built. Metadata and targets in ./release")
