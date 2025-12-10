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
from itertools import product
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

        # Keep only non-empty lines for mapping; line numbers reference original files.
        keep_old = [i for i, l in enumerate(self.old_lines) if l.strip()]
        keep_new = [j for j, l in enumerate(self.new_lines) if l.strip()]
        norm_old = [self._normalize(self.old_lines[i]) for i in keep_old]
        norm_new = [self._normalize(self.new_lines[j]) for j in keep_new]

        # Precompute tokens, contexts, and simhashes on kept lines.
        old_tokens = [Counter(self._tokens(t)) for t in norm_old]
        new_tokens = [Counter(self._tokens(t)) for t in norm_new]

        def ctx_tokens(tokens_list: List[Counter], idx: int) -> Counter:
            start = max(0, idx - 4)
            end = min(len(tokens_list), idx + 5)
            combined = Counter()
            for c in tokens_list[start:end]:
                combined.update(c)
            return combined

        old_ctx_tokens = [ctx_tokens(old_tokens, i) for i in range(len(old_tokens))]
        new_ctx_tokens = [ctx_tokens(new_tokens, j) for j in range(len(new_tokens))]
        old_hashes = [self._simhash(" ".join(self._tokens(t))) for t in norm_old]
        new_hashes = [self._simhash(" ".join(self._tokens(t))) for t in norm_new]

        sm = difflib.SequenceMatcher(a=norm_old, b=norm_new, autojunk=False)
        mapped_old = set()
        mapped_new = set()
        opcodes = sm.get_opcodes()
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                for k in range(i2 - i1):
                    oi = i1 + k
                    nj = j1 + k
                    mappings.append(LineMapping(old_line=keep_old[oi] + 1, new_line=keep_new[nj] + 1))
                    mapped_old.add(oi)
                    mapped_new.add(nj)
            elif tag == "replace":
                block_old = list(range(i1, i2))
                block_new = list(range(j1, j2))
                # Build similarity matrix with positional bonus.
                sim_matrix: List[List[float]] = []
                for oi_idx, oi in enumerate(block_old):
                    row = []
                    for nj_idx, nj in enumerate(block_new):
                        content_sim = self._tf_cosine(old_tokens[oi], new_tokens[nj])
                        context_sim = self._tf_cosine(old_ctx_tokens[oi], new_ctx_tokens[nj])
                        pos_bonus = 0.2 if abs(oi_idx - nj_idx) <= 1 else 0.0
                        base = 0.7 * content_sim + 0.3 * context_sim
                        row.append(base + pos_bonus if base >= 0.05 else base)
                    sim_matrix.append(row)

                assignment = self._max_assignment(sim_matrix)
                used_old = set()
                used_new = set()
                for oi_idx, nj_idx in assignment:
                    score = sim_matrix[oi_idx][nj_idx]
                    if score < 0.1:
                        continue
                    oi = block_old[oi_idx]
                    nj = block_new[nj_idx]
                    used_old.add(oi)
                    used_new.add(nj)
                    mapped_old.add(oi)
                    mapped_new.add(nj)
                    mappings.append(LineMapping(old_line=keep_old[oi] + 1, new_line=keep_new[nj] + 1))

                for oi in block_old:
                    if oi not in used_old:
                        mappings.append(LineMapping(old_line=keep_old[oi] + 1, new_line=None))
                        mapped_old.add(oi)
                for nj in block_new:
                    if nj not in used_new:
                        mappings.append(LineMapping(old_line=None, new_line=keep_new[nj] + 1))
                        mapped_new.add(nj)
            elif tag == "delete":
                for oi in range(i1, i2):
                    if oi not in mapped_old:
                        mappings.append(LineMapping(old_line=keep_old[oi] + 1, new_line=None))
                        mapped_old.add(oi)
            elif tag == "insert":
                for nj in range(j1, j2):
                    if nj not in mapped_new:
                        mappings.append(LineMapping(old_line=None, new_line=keep_new[nj] + 1))
                        mapped_new.add(nj)
            else:  # pragma: no cover
                raise ValueError(f"Unexpected tag: {tag}")

        mappings.sort(key=lambda m: (m.old_line is None, m.old_line if m.old_line is not None else float("inf"),
                                     m.new_line if m.new_line is not None else float("inf")))
        return mappings

    @staticmethod
    def _max_assignment(sim_matrix: List[List[float]]) -> List[tuple[int, int]]:
        """Hungarian algorithm for maximum weight matching on a rectangular matrix."""
        if not sim_matrix or not sim_matrix[0]:
            return []
        n_rows = len(sim_matrix)
        n_cols = len(sim_matrix[0])
        n = max(n_rows, n_cols)
        max_val = max(max(row) for row in sim_matrix) if sim_matrix else 0
        # Build square cost matrix for minimization.
        cost = [[max_val - (sim_matrix[i][j] if i < n_rows and j < n_cols else 0) for j in range(n)] for i in range(n)]
        u = [0] * (n + 1)
        v = [0] * (n + 1)
        p = [0] * (n + 1)
        way = [0] * (n + 1)
        INF = float("inf")
        for i in range(1, n + 1):
            p[0] = i
            j0 = 0
            minv = [INF] * (n + 1)
            used = [False] * (n + 1)
            while True:
                used[j0] = True
                i0 = p[j0]
                delta = INF
                j1 = 0
                for j in range(1, n + 1):
                    if used[j]:
                        continue
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
                for j in range(n + 1):
                    if used[j]:
                        u[p[j]] += delta
                        v[j] -= delta
                    else:
                        minv[j] -= delta
                j0 = j1
                if p[j0] == 0:
                    break
            while True:
                j1 = way[j0]
                p[j0] = p[j1]
                j0 = j1
                if j0 == 0:
                    break
        # Extract assignment
        assignment = []
        for j in range(1, n + 1):
            if p[j] and p[j] - 1 < n_rows and j - 1 < n_cols:
                assignment.append((p[j] - 1, j - 1))
        return assignment

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
