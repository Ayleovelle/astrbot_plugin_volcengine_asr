from __future__ import annotations

import csv
import importlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


TEST_MODULES = ("tests.test_helpers", "tests.test_voice_workflow")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_direct_tests() -> tuple[int, str]:
    import tests.conftest  # noqa: F401

    count = 0
    for module_name in TEST_MODULES:
        module = importlib.import_module(module_name)
        for name in sorted(dir(module)):
            if not name.startswith("test_"):
                continue
            func = getattr(module, name)
            if callable(func):
                func()
                count += 1
    return count, "ok"


def main(argv: list[str]) -> int:
    rounds = int(argv[1]) if len(argv) > 1 else 1
    log_path = Path(argv[2]) if len(argv) > 2 else Path("output/local_iteration_rounds.csv")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists()

    with log_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["round", "start", "end", "duration_ms", "tests", "status", "error"])
        if write_header:
            writer.writeheader()
        for index in range(1, rounds + 1):
            start_time = time.perf_counter()
            start = datetime.now(timezone.utc).isoformat()
            tests = 0
            status = "ok"
            error = ""
            try:
                tests, status = run_direct_tests()
            except Exception as exc:
                status = "failed"
                error = f"{exc.__class__.__name__}: {exc}"
            end = datetime.now(timezone.utc).isoformat()
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            writer.writerow(
                {
                    "round": index,
                    "start": start,
                    "end": end,
                    "duration_ms": duration_ms,
                    "tests": tests,
                    "status": status,
                    "error": error,
                }
            )
            handle.flush()
            print(f"round={index} status={status} tests={tests} duration_ms={duration_ms}")
            if status != "ok":
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
