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
        """Return a list of line correspondences using a hybrid LHDiff-style approach."""
        mappings: List[LineMapping] = []

        # Step 1: anchor unchanged lines using diff on normalized text.
        sm = difflib.SequenceMatcher(a=self._norm_old, b=self._norm_new, autojunk=False)
        matched_old = set()
        matched_new = set()
        opcodes = sm.get_opcodes()
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                for k in range(i2 - i1):
                    oi = i1 + k
                    nj = j1 + k
                    mappings.append(LineMapping(old_line=oi + 1, new_line=nj + 1))
                    matched_old.add(oi)
                    matched_new.add(nj)

        # Step 2: build candidate mappings for unmatched blocks using similarity.
        proposals: List[tuple[float, int, int]] = []
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                continue
            block_old = [i for i in range(i1, i2) if i not in matched_old]
            block_new = [j for j in range(j1, j2) if j not in matched_new]
            if not block_old or not block_new:
                continue
            for oi in block_old:
                scores: List[tuple[float, int]] = []
                for nj in block_new:
                    content_sim = difflib.SequenceMatcher(None, self._norm_old[oi], self._norm_new[nj]).ratio()
                    context_sim = self._context_similarity(oi, nj)
                    combined = 0.6 * content_sim + 0.4 * context_sim
                    scores.append((combined, nj))
                # take top-k candidates by combined score to mimic simhash pruning
                scores.sort(key=lambda x: x[0], reverse=True)
                for combined, nj in scores[:15]:
                    if combined >= 0.3:
                        proposals.append((combined, oi, nj))

        # Step 3: resolve conflicts by highest score first.
        proposals.sort(key=lambda x: x[0], reverse=True)
        for score, oi, nj in proposals:
            if oi in matched_old or nj in matched_new:
                continue
            matched_old.add(oi)
            matched_new.add(nj)
            mappings.append(LineMapping(old_line=oi + 1, new_line=nj + 1))

        # Step 4: mark remaining unmatched as insert/delete.
        for oi in range(len(self.old_lines)):
            if oi not in matched_old:
                mappings.append(LineMapping(old_line=oi + 1, new_line=None))
        for nj in range(len(self.new_lines)):
            if nj not in matched_new:
                mappings.append(LineMapping(old_line=None, new_line=nj + 1))

        # keep deterministic ordering by old/new line numbers
        mappings.sort(key=lambda m: (m.old_line is None, m.old_line if m.old_line is not None else float("inf"),
                                     m.new_line if m.new_line is not None else float("inf")))
        return mappings

    def _context_similarity(self, oi: int, nj: int) -> float:
        """Compute a rough context similarity using adjacent normalized lines."""
        old_ctx = " ".join(self._norm_old[max(0, oi - 1): min(len(self._norm_old), oi + 2)])
        new_ctx = " ".join(self._norm_new[max(0, nj - 1): min(len(self._norm_new), nj + 2)])
        if not old_ctx or not new_ctx:
            return 0.0
        return difflib.SequenceMatcher(None, old_ctx, new_ctx).ratio()

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
