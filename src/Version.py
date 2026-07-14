import os
import sys

from packaging.version import Version as SemVer


VERSION = "2.3.3"  # Update this when releasing new versions
LINUX_VERSION_FILENAME = ".telemetry-version"


def resolve_running_version(
    bundled_version: str = VERSION,
    app_install_dir: str | None = None,
    platform_name: str | None = None,
) -> str:
    """Return the successfully installed bundle version on Linux.

    Other platforms always use the version embedded by PyInstaller. The
    optional platform argument exists so the platform boundary can be tested
    without changing the running interpreter.
    """
    platform_name = platform_name or sys.platform
    if not platform_name.startswith("linux") or not app_install_dir:
        return bundled_version

    marker_path = os.path.join(app_install_dir, LINUX_VERSION_FILENAME)
    try:
        with open(marker_path, "r", encoding="utf-8") as file:
            installed_version = file.read().strip()
        installed_semver = SemVer(installed_version)
        try:
            bundled_semver = SemVer(bundled_version)
        except (ValueError, TypeError):
            return installed_version
        # A manually replaced bundle may leave an older marker behind. Prefer
        # the embedded version in that case; the marker's purpose is to repair
        # releases whose embedded constant is older than the installed bundle.
        return installed_version if installed_semver >= bundled_semver else bundled_version
    except (OSError, ValueError, TypeError):
        return bundled_version
