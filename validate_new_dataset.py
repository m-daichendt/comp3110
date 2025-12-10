#!/usr/bin/env python3
"""
Validate mappings stored in a generated dataset JSON against the current LineMapper.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Optional

from line_mapper import LineMapper


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate new_test_data.json against line_mapper.py")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("new_test_data.json"),
        help="Path to the generated dataset JSON (default: new_test_data.json)",
    )
    return parser.parse_args(argv)


def mapping_for_files(old_path: Path, new_path: Path) -> dict[int, Optional[int]]:
    old_lines = old_path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = new_path.read_text(encoding="utf-8").splitlines(keepends=True)
    result: dict[int, Optional[int]] = {}
    for m in LineMapper(old_lines, new_lines).map_lines():
        if m.old_line is None:
            continue
        # keep first occurrence to allow many-to-one mappings
        result.setdefault(m.old_line, m.new_line)
    return result


def validate(dataset_path: Path) -> tuple[int, int, List[str]]:
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    failures: List[str] = []
    for entry in data:
        old_file = Path(entry["old_file"])
        new_file = Path(entry["new_file"])
        expected = {m["orig"]: m["new"] for m in entry["mappings"] if m["orig"] is not None}
        actual = mapping_for_files(old_file, new_file)
        pair_failures = []
        for orig, exp_new in expected.items():
            act_new = actual.get(orig)
            if act_new != exp_new:
                pair_failures.append(f"{old_file.name} -> {new_file.name} orig {orig}: expected {exp_new}, got {act_new}")
        if pair_failures:
            failed += 1
            failures.extend(pair_failures)
        else:
            passed += 1
    return passed, failed, failures


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    passed, failed, failures = validate(args.dataset)
    output_lines: List[str] = []
    if failures:
        output_lines.append("FAILED:")
        for f in failures:
            output_lines.append(f" - {f}")
        output_lines.append(f"\nSummary: {passed + failed} pairs validated; {passed} passed, {failed} failed.")
        print("\n".join(output_lines))
        Path("validate_new_data_results.txt").write_text("\n".join(output_lines), encoding="utf-8")
        return 1
    msg = f"All {passed} pairs validated successfully."
    print(msg)
    Path("validate_new_data_results.txt").write_text(msg + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
