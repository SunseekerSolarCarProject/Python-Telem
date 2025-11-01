import math
from datetime import datetime
from copy import deepcopy


class QualityDiagnostics:
    """
    Aggregate helper that turns model prediction metadata into concise
    quality signals for the GUI / downstream logging.
    """

    def __init__(self, stale_threshold_seconds: float = 5.0):
        self.stale_threshold_seconds = stale_threshold_seconds

    def _compute_age(self, timestamp_str: str | None) -> float | None:
        if not timestamp_str:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                ts = datetime.strptime(timestamp_str, fmt)
                delta = datetime.now() - ts
                return max(delta.total_seconds(), 0.0)
            except ValueError:
                continue
        return None

    def evaluate(self, timestamp_str: str | None, battery: dict | None, break_even: dict | None) -> dict:
        """
        Build a diagnostics summary.
        """
        battery = deepcopy(battery) if battery else {}
        break_even = deepcopy(break_even) if break_even else {}

        age = self._compute_age(timestamp_str)
        flags: list[str] = []

        if age is not None and self.stale_threshold_seconds and age > self.stale_threshold_seconds:
            flags.append(f"stale-data ({age:.1f}s old)")

        def _expand_flags(prefix: str, details: dict):
            if not details:
                return
            missing = details.get("missing_features") or []
            if missing:
                flags.append(f"{prefix} missing: {', '.join(missing)}")
            invalid = details.get("invalid_features") or []
            if invalid:
                flags.append(f"{prefix} invalid: {', '.join(invalid)}")
            outliers = details.get("out_of_range") or {}
            if outliers:
                bad = ", ".join(f"{k} (got {v['value']:.2f}, expected {v['min']:.2f}-{v['max']:.2f})"
                                for k, v in outliers.items())
                flags.append(f"{prefix} out-of-range: {bad}")
            if details.get("not_fitted"):
                flags.append(f"{prefix} model not fitted")
            if details.get("error"):
                flags.append(f"{prefix} error: {details['error']}")

        _expand_flags("battery", battery)
        _expand_flags("break-even", break_even)

        def _confidence(details: dict):
            sigma = details.get("sigma")
            if sigma is None:
                return None
            if not isinstance(sigma, (int, float)) or math.isnan(sigma):
                return None
            return float(sigma)

        return {
            "age_seconds": age,
            "flags": flags,
            "battery_sigma": _confidence(battery),
            "break_even_sigma": _confidence(break_even),
            "battery": battery,
            "break_even": break_even,
        }
