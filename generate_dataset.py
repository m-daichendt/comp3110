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
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from line_mapper import LineMapper, LineMapping


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a 25-pair, ~500-line mapping dataset from local files."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Root directory to search for files; if omitted and --repo-url is provided, the repo will be cloned to a temp dir.",
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
        default=Path("new_test_data.json"),
        help="Path to write the generated dataset (default: new_test_data.json)",
    )
    parser.add_argument(
        "--copy-files",
        action="store_true",
        help="If set, copy paired files into a local new-test-data directory mirroring test-data structure.",
    )
    parser.add_argument(
        "--repo-url",
        help="Git repository URL (e.g., https://github.com/owner/repo.git). If set, the repo is cloned to a temp directory for dataset generation.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Optional branch or commit to check out when cloning the repo.",
    )
    return parser.parse_args(argv)


def clone_repo(url: str, branch: Optional[str] = None) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="dataset_repo_"))
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd.extend(["--branch", branch])
    cmd.extend([url, str(temp_dir)])
    subprocess.run(cmd, check=True)
    return temp_dir


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


def copy_pair_files(pairs: List[dict], dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for entry in pairs:
        old_src = Path(entry["old_file"])
        new_src = Path(entry["new_file"])
        old_dest = dest_root / f"{old_src.stem}_old{old_src.suffix}"
        new_dest = dest_root / f"{new_src.stem}_new{new_src.suffix}"
        old_dest.write_bytes(old_src.read_bytes())
        new_dest.write_bytes(new_src.read_bytes())
        entry["old_file"] = str(old_dest)
        entry["new_file"] = str(new_dest)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    root_dir: Optional[Path] = args.root
    cloned_dir: Optional[Path] = None
    try:
        if args.repo_url:
            cloned_dir = clone_repo(args.repo_url, args.branch)
            root_dir = cloned_dir
        if root_dir is None:
            root_dir = Path(".")

        dataset = build_dataset(root_dir, args.glob, args.pairs, args.target_lines, args.seed)
        args.output.write_text(
            __import__("json").dumps(dataset, indent=2),
            encoding="utf-8",
        )
        print(
            f"Wrote {len(dataset)} pairs to {args.output} with total mappings capped at {args.target_lines}."
        )
        return 0
    finally:
        if cloned_dir and cloned_dir.exists():
            shutil.rmtree(cloned_dir)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
