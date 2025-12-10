#!/usr/bin/env python3
"""
Line mapping tool: given old and new file versions, report mapping of old line numbers to new line numbers.
"""

from __future__ import annotations

import argparse
import difflib
import math
import re
from collections import Counter
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
        self._norm_old = [self._normalize(l) for l in self.old_lines]
        self._norm_new = [self._normalize(l) for l in self.new_lines]

    @staticmethod
    def _normalize(line: str) -> str:
        """Lightweight normalization: lowercase and collapse whitespace."""
        return " ".join(line.lower().split())

    @staticmethod
    def _tokens(text: str) -> List[str]:
        """Simple alphanumeric tokenization."""
        return re.findall(r"[a-zA-Z0-9_]+", text.lower())

    @staticmethod
    def _tf_cosine(t1: Counter, t2: Counter) -> float:
        """Cosine similarity between two token frequency counters."""
        if not t1 or not t2:
            return 0.0
        dot = sum(t1[k] * t2.get(k, 0) for k in t1)
        if dot == 0:
            return 0.0
        norm1 = math.sqrt(sum(v * v for v in t1.values()))
        norm2 = math.sqrt(sum(v * v for v in t2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    @staticmethod
    def _simhash(text: str) -> int:
        """Compute a simple 64-bit simhash from token hashes."""
        if not text:
            return 0
        weights = [0] * 64
        for token in text.split():
            h = hash(token)
            for i in range(64):
                bit = (h >> i) & 1
                weights[i] += 1 if bit else -1
        result = 0
        for i, w in enumerate(weights):
            if w >= 0:
                result |= (1 << i)
        return result

    @staticmethod
    def _hamming(a: int, b: int) -> int:
        return (a ^ b).bit_count()

    def map_lines(self) -> List[LineMapping]:
        """Return a list of line correspondences using a closer LHDiff-style approach."""
        mappings: List[LineMapping] = []

        # Precompute normalized tokens, contexts, and simhashes.
        old_tokens = [Counter(self._tokens(t)) for t in self._norm_old]
        new_tokens = [Counter(self._tokens(t)) for t in self._norm_new]

        def ctx_tokens(tokens_list: List[Counter], idx: int) -> Counter:
            start = max(0, idx - 4)
            end = min(len(tokens_list), idx + 5)
            combined = Counter()
            for c in tokens_list[start:end]:
                combined.update(c)
            return combined

        old_ctx_tokens = [ctx_tokens(old_tokens, i) for i in range(len(old_tokens))]
        new_ctx_tokens = [ctx_tokens(new_tokens, j) for j in range(len(new_tokens))]
        old_hashes = [self._simhash(" ".join(self._tokens(t))) for t in self._norm_old]
        new_hashes = [self._simhash(" ".join(self._tokens(t))) for t in self._norm_new]

        # Step 1: anchor unchanged lines using diff on normalized text.
        sm = difflib.SequenceMatcher(a=self._norm_old, b=self._norm_new, autojunk=False)
        matched_old = set()
        matched_new = set()
        opcodes = sm.get_opcodes()
        for tag, i1, i2, j1, j2 in opcodes:
            if tag != "equal":
                continue
            for k in range(i2 - i1):
                oi = i1 + k
                nj = j1 + k
                mappings.append(LineMapping(old_line=oi + 1, new_line=nj + 1))
                matched_old.add(oi)
                matched_new.add(nj)

        # Step 2: candidate mappings for unmatched lines using simhash pruning (content+context).
        proposals: List[tuple[float, int, int]] = []
        unmatched_old = [i for i in range(len(self._norm_old)) if i not in matched_old]
        unmatched_new = [j for j in range(len(self._norm_new)) if j not in matched_new]

        for oi in unmatched_old:
            # rank all unmatched new lines by combined hamming distance of content and context simhash
            ranked = sorted(
                (
                    self._hamming(old_hashes[oi], new_hashes[nj])
                    + self._hamming(self._simhash(" ".join(old_ctx_tokens[oi].elements())),
                                    self._simhash(" ".join(new_ctx_tokens[nj].elements()))),
                    nj,
                )
                for nj in unmatched_new
            )
            top_candidates = [nj for _, nj in ranked[:15]]
            scored: List[tuple[float, int]] = []
            for nj in top_candidates:
                content_sim = self._tf_cosine(old_tokens[oi], new_tokens[nj])
                context_sim = self._tf_cosine(old_ctx_tokens[oi], new_ctx_tokens[nj])
                combined = 0.6 * content_sim + 0.4 * context_sim
                scored.append((combined, nj))
            scored.sort(key=lambda x: x[0], reverse=True)
            for combined, nj in scored:
                if combined >= 0.5:
                    proposals.append((combined, oi, nj))

        # Step 3: resolve conflicts greedily by score.
        proposals.sort(key=lambda x: x[0], reverse=True)
        for score, oi, nj in proposals:
            if oi in matched_old or nj in matched_new:
                continue
            matched_old.add(oi)
            matched_new.add(nj)
            mappings.append(LineMapping(old_line=oi + 1, new_line=nj + 1))

        # Step 4: mark remaining unmatched as insert/delete.
        for oi in unmatched_old:
            if oi not in matched_old:
                mappings.append(LineMapping(old_line=oi + 1, new_line=None))
        for nj in unmatched_new:
            if nj not in matched_new:
                mappings.append(LineMapping(old_line=None, new_line=nj + 1))

        mappings.sort(key=lambda m: (m.old_line is None, m.old_line if m.old_line is not None else float("inf"),
                                     m.new_line if m.new_line is not None else float("inf")))
        return mappings

    def _context_similarity(self, oi: int, nj: int) -> float:
        """Compute a rough context similarity using adjacent normalized lines."""
        # Deprecated in favor of token-based cosine; retained for compatibility.
        old_ctx = " ".join(self._norm_old[max(0, oi - 4): min(len(self._norm_old), oi + 5)])
        new_ctx = " ".join(self._norm_new[max(0, nj - 4): min(len(self._norm_new), nj + 5)])
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
