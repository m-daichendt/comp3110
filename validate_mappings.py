#!/usr/bin/env python3
"""Validate generated line mappings against the provided test_data.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from line_mapper import LineMapper


def mapping_for_files(old_path: Path, new_path: Path) -> Dict[int, Optional[int]]:
    """Return a mapping of old line -> new line (or None) for two files."""
    old_lines = old_path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = new_path.read_text(encoding="utf-8").splitlines(keepends=True)
    mappings = LineMapper(old_lines, new_lines).map_lines()
    result: Dict[int, Optional[int]] = {}
    for m in mappings:
        if m.old_line is None:
            continue
        if m.old_line in result:  # pragma: no cover - defensive
            raise ValueError(f"Duplicate mapping for line {m.old_line}")
        result[m.old_line] = m.new_line
    return result


def validate_test_case(test: dict) -> List[str]:
    """Validate all versions in a single test case, returning failure messages."""
    versions = test["versions"]
    base = next((v for v in versions if v["number"] == 1 and v["java_path"]), None)
    if base is None:
        return [f"{test['name']}: missing base version 1 file"]

    base_path = Path(base["java_path"])
    failures: List[str] = []
    for version in versions:
        if version["number"] == 1:
            continue
        if not version["java_path"]:
            failures.append(f"{test['name']} v{version['number']}: missing java file")
            continue

        target_path = Path(version["java_path"])
        actual_map = mapping_for_files(base_path, target_path)
        for loc in version["locations"]:
            expected_new = loc["new"]
            orig_line = loc["orig"]
            actual_new = actual_map.get(orig_line)
            if actual_new != expected_new:
                failures.append(
                    f"{test['name']} v{version['number']} orig {orig_line}: "
                    f"expected {expected_new}, got {actual_new}"
                )
    return failures


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run test_data.json against line_mapper.py to ensure mappings match expected."
    )
    parser.add_argument(
        "json_path",
        nargs="?",
        default=Path("test_data.json"),
        help="Path to test_data.json (defaults to test_data.json)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    data = json.loads(Path(args.json_path).read_text(encoding="utf-8"))

    all_failures: List[str] = []
    for test in data:
        all_failures.extend(validate_test_case(test))

    if all_failures:
        print("FAILED:")
        for failure in all_failures:
            print(f" - {failure}")
        return 1

    print(f"All {len(data)} test cases passed.")
    return 0


if __name__ == "__main__":  
    raise SystemExit(main())# pragma: no cover
