#!/usr/bin/env python3
"""
Generate a validation dataset of line mappings across file pairs.

Constraints:
 - Produce mappings for 25 pairs of files (or fewer if not enough files).
 - Total mapped lines across all pairs capped at 500.
 - Files are selected locally from a provided root and glob pattern (no network fetch).
 - Uses the current LineMapper to compute mappings.
 - Output is written to `new_dataset.json` in the project root.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Iterable, List, Sequence

from line_mapper import LineMapper, LineMapping


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 25-pair, ~500-line mapping dataset from local files."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Root directory to search for files (default: current directory)",
    )
    parser.add_argument(
        "--glob",
        default="**/*.java",
        help="Glob pattern to select files relative to root (default: **/*.java)",
    )
    parser.add_argument(
        "--pairs",
        type=int,
        default=25,
        help="Number of file pairs to include (default: 25)",
    )
    parser.add_argument(
        "--target-lines",
        type=int,
        default=500,
        help="Target total mapped lines across all pairs (default: 500)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic sampling (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("new_dataset.json"),
        help="Path to write the generated dataset (default: new_dataset.json)",
    )
    return parser.parse_args(argv)


def sample_pairs(files: Sequence[Path], pairs: int, seed: int) -> List[tuple[Path, Path]]:
    rng = random.Random(seed)
    selectable = list(files)
    rng.shuffle(selectable)
    result: List[tuple[Path, Path]] = []
    # pair consecutive files to keep it simple/deterministic after shuffle
    for i in range(0, min(len(selectable) - 1, pairs * 2), 2):
        result.append((selectable[i], selectable[i + 1]))
        if len(result) >= pairs:
            break
    return result


def truncate_mappings(mappings: List[LineMapping], remaining: int) -> List[LineMapping]:
    return mappings[:remaining]


def build_dataset(root: Path, glob: str, pairs: int, target_lines: int, seed: int) -> List[dict]:
    files = sorted(root.glob(glob))
    if len(files) < 2:
        raise SystemExit("Not enough files found to create pairs.")

    dataset: List[dict] = []
    total_added = 0
    for idx, (a_path, b_path) in enumerate(sample_pairs(files, pairs, seed), 1):
        if total_added >= target_lines:
            break
        a_lines = a_path.read_text(encoding="utf-8").splitlines(keepends=True)
        b_lines = b_path.read_text(encoding="utf-8").splitlines(keepends=True)
        mapper = LineMapper(a_lines, b_lines)
        mappings = mapper.map_lines()
        remaining = target_lines - total_added
        trimmed = truncate_mappings(mappings, remaining)
        total_added += len(trimmed)
        dataset.append(
            {
                "pair": idx,
                "old_file": str(a_path),
                "new_file": str(b_path),
                "mappings": [{"orig": m.old_line, "new": m.new_line} for m in trimmed],
            }
        )
    return dataset


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    dataset = build_dataset(args.root, args.glob, args.pairs, args.target_lines, args.seed)
    args.output.write_text(
        __import__("json").dumps(dataset, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(dataset)} pairs to {args.output} with total mappings capped at {args.target_lines}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
