from __future__ import annotations

import importlib
import inspect
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    failures: list[str] = []
    for path in sorted(Path(__file__).parent.glob("test_*.py")):
        module = importlib.import_module(path.stem)
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            try:
                if "tmp_path" in inspect.signature(function).parameters:
                    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
                        function(Path(directory))
                else:
                    function()
            except Exception as exc:  # noqa: BLE001 - test runner reports any failure.
                failures.append(f"{path.name}::{name}: {exc}")

    if failures:
        print("\n".join(failures))
        return 1
    print("All tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
