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
        # Normalized copies used for similarity/diff decisions.
        self._norm_old = [self._normalize(l) for l in self.old_lines]
        self._norm_new = [self._normalize(l) for l in self.new_lines]

    @staticmethod
    def _normalize(line: str) -> str:
        """Lightweight normalization: lowercase and collapse whitespace."""
        return " ".join(line.lower().split())

    def map_lines(self) -> List[LineMapping]:
        """Return a list of line correspondences derived from difflib opcodes."""
        sm = difflib.SequenceMatcher(a=self._norm_old, b=self._norm_new, autojunk=False)
        mappings: List[LineMapping] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    mappings.append(LineMapping(old_line=i1 + k + 1, new_line=j1 + k + 1))
            elif tag == "replace":
                # Use similarity to pair lines in replace blocks; unmatched are delete/insert.
                pairings = self._greedy_pair(i1, i2, j1, j2)
                mapped_old = set()
                mapped_new = set()
                for oi, nj in pairings:
                    mappings.append(LineMapping(old_line=oi + 1, new_line=nj + 1))
                    mapped_old.add(oi)
                    mapped_new.add(nj)
                for oi in range(i1, i2):
                    if oi not in mapped_old:
                        mappings.append(LineMapping(old_line=oi + 1, new_line=None))
                for nj in range(j1, j2):
                    if nj not in mapped_new:
                        mappings.append(LineMapping(old_line=None, new_line=nj + 1))
            elif tag == "delete":
                for k in range(i1, i2):
                    mappings.append(LineMapping(old_line=k + 1, new_line=None))
            elif tag == "insert":
                for k in range(j1, j2):
                    mappings.append(LineMapping(old_line=None, new_line=k + 1))
            else:  # pragma: no cover
                raise ValueError(f"Unexpected tag: {tag}")
        return mappings

    def _greedy_pair(self, i1: int, i2: int, j1: int, j2: int) -> List[tuple[int, int]]:
        """Pair lines in replace blocks using similarity, highest first."""
        pairs: List[tuple[int, int, float]] = []
        for oi in range(i1, i2):
            for nj in range(j1, j2):
                score = difflib.SequenceMatcher(None, self._norm_old[oi], self._norm_new[nj]).ratio()
                pairs.append((oi, nj, score))
        # Sort by descending score
        pairs.sort(key=lambda x: x[2], reverse=True)
        used_old = set()
        used_new = set()
        chosen: List[tuple[int, int]] = []
        for oi, nj, score in pairs:
            if score < 0.4:  # ignore weak matches
                break
            if oi in used_old or nj in used_new:
                continue
            used_old.add(oi)
            used_new.add(nj)
            chosen.append((oi, nj))
        return chosen

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
