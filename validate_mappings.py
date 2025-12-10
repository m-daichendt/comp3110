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
    """Validate adjacent version mappings in a single test case."""
    versions = sorted(test["versions"], key=lambda v: v["number"])
    failures: List[str] = []

    for prev, current in zip(versions, versions[1:]):
        if not prev["java_path"]:
            failures.append(f"{test.get('file', '<unknown>')} v{prev['number']}: missing java file")
            continue
        if not current["java_path"]:
            failures.append(f"{test.get('file', '<unknown>')} v{current['number']}: missing java file")
            continue

        prev_path = Path(prev["java_path"])
        current_path = Path(current["java_path"])
        actual_map = mapping_for_files(prev_path, current_path)
        for loc in current["locations"]:
            expected_new = loc["new"]
            orig_line = loc["orig"]
            actual_new = actual_map.get(orig_line)
            if actual_new != expected_new:
                failures.append(
                    f"{test.get('file', '<unknown>')} v{prev['number']} -> v{current['number']} orig {orig_line}: "
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
    total_cases = 0
    failed_cases = 0
    for test in data:
        total_cases += 1
        failures = validate_test_case(test)
        if failures:
            failed_cases += 1
            all_failures.extend(failures)

    if all_failures:
        print("FAILED:")
        for failure in all_failures:
            print(f" - {failure}")
        success_cases = total_cases - failed_cases
        print(f"\nSummary: {success_cases}/{total_cases} cases passed; {failed_cases} failed.")
        return 1

    print(f"All {total_cases} test cases passed.")
    return 0


if __name__ == "__main__":  
    raise SystemExit(main())# pragma: no cover
