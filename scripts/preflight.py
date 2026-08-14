from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from atlas_workforce.config.settings import load_settings  # noqa: E402
from atlas_workforce.preflight import run_preflight  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local project readiness.")
    parser.add_argument("--config", type=Path, default=ROOT / "config.yaml")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()

    settings = load_settings(args.config)
    checks = run_preflight(settings, ROOT, args.env)

    for check in checks:
        mark = "PASS" if check.passed else "FAIL"
        print(f"[{mark}] {check.name}: {check.message}")

    failed = [check for check in checks if not check.passed]
    if failed:
        print(f"\nPreflight failed: {len(failed)} check(s) need attention.")
        raise SystemExit(1)
    print("\nPreflight passed.")


if __name__ == "__main__":
    main()
