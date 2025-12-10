#!/usr/bin/env python3
"""
Line mapping tool: given old and new file versions, report mapping of old line numbers to new line numbers.
"""

from __future__ import annotations

import argparse
import difflib
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class LineMapping:
    """Represents a single correspondence between an old and new line number."""
    old_line: int | None
    new_line: int | None

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"old:{self.old_line} -> new:{self.new_line}"


class LineMapper:
    def __init__(self, old_lines: Sequence[str], new_lines: Sequence[str]):
        """Store the sequences that will be diffed to derive line mappings."""
        self.old_lines = list(old_lines)
        self.new_lines = list(new_lines)

    def map_lines(self) -> List[LineMapping]:
        """Return a list of line correspondences derived from difflib opcodes."""
        sm = difflib.SequenceMatcher(a=self.old_lines, b=self.new_lines, autojunk=False)
        mappings: List[LineMapping] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    mappings.append(LineMapping(old_line=i1 + k + 1, new_line=j1 + k + 1))
            elif tag == "replace":
                for k in range(i1, i2):
                    mappings.append(LineMapping(old_line=k + 1, new_line=None))
                for k in range(j1, j2):
                    mappings.append(LineMapping(old_line=None, new_line=k + 1))
            elif tag == "delete":
                for k in range(i1, i2):
                    mappings.append(LineMapping(old_line=k + 1, new_line=None))
            elif tag == "insert":
                for k in range(j1, j2):
                    mappings.append(LineMapping(old_line=None, new_line=k + 1))
            else:  # pragma: no cover
                raise ValueError(f"Unexpected tag: {tag}")
        return mappings

    def pretty_mapping(self) -> str:
        """Human-readable mapping like `4 -> 6` with `-` for inserts/deletes."""
        parts = []
        for m in self.map_lines():
            parts.append(f"{m.old_line if m.old_line is not None else '-'} -> {m.new_line if m.new_line is not None else '-'}")
        return "\n".join(parts)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """CLI argument parsing wrapper to keep `main` focused on work."""
    parser = argparse.ArgumentParser(description="Map line numbers from old file to new file using diffs.")
    parser.add_argument("old_file", help="Path to the old version of the file")
    parser.add_argument("new_file", help="Path to the new version of the file")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    """Entry point for the command-line tool."""
    args = parse_args(argv)
    with open(args.old_file, "r", encoding="utf-8") as f:
        old_lines = f.readlines()
    with open(args.new_file, "r", encoding="utf-8") as f:
        new_lines = f.readlines()

    mapper = LineMapper(old_lines, new_lines)
    print(mapper.pretty_mapping())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
