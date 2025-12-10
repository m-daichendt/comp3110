#!/usr/bin/env python3
"""
Generate a validation dataset by comparing files across recent commits of a GitHub repository.

Behavior:
 - Repo URL is mandatory; the repository is cloned to a temporary directory (depth 1 + needed history).
 - For each file at HEAD, compare it to its versions in the last N commits (default 1: HEAD vs HEAD~1).
 - Produce up to 25 file/commit pairs, capped at 500 total mapped lines.
 - Outputs dataset to `new_test_data.json` by default.
 - With `--copy-files`, writes the paired file contents into `new-test-data/` for inspection.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from line_mapper import LineMapper, LineMapping


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate dataset by comparing files across recent commits of a Git repository."
    )
    parser.add_argument(
        "--repo-url",
        required=True,
        help="Git repository URL (e.g., https://github.com/owner/repo.git).",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Optional branch or commit to check out (default: repo default).",
    )
    parser.add_argument(
        "--commits",
        type=int,
        default=1,
        help="Number of recent commit pairs to compare per file (default: 1, i.e., HEAD vs HEAD~1).",
    )
    parser.add_argument(
        "--glob",
        default="**/*.py",
        help="Glob pattern (fnmatch-style on repo paths) to select files (default: **/*.py).",
    )
    parser.add_argument(
        "--pairs",
        type=int,
        default=25,
        help="Maximum number of file/commit pairs to include (default: 25).",
    )
    parser.add_argument(
        "--target-lines",
        type=int,
        default=500,
        help="Cap total mapped lines across all pairs (default: 500).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic sampling (default: 42).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("new_test_data.json"),
        help="Path to write the generated dataset (default: new_test_data.json).",
    )
    parser.add_argument(
        "--copy-files",
        action="store_true",
        help="If set, copy paired file contents into new-test-data/ for inspection.",
    )
    return parser.parse_args(argv)


def _on_rm_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_git(repo_dir: Path, args: List[str]) -> str:
    result = subprocess.run(["git", "-C", str(repo_dir), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def clone_repo(url: str, branch: Optional[str]) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="dataset_repo_"))
    cmd = ["git", "clone", url, str(temp_dir)]
    if branch:
        cmd.extend(["--branch", branch])
    subprocess.run(cmd, check=True)
    return temp_dir


def recent_commits(repo_dir: Path, count: int) -> List[str]:
    # Need count+1 commits to form count pairs (HEAD vs HEAD~1, HEAD~1 vs HEAD~2, etc.)
    log = run_git(repo_dir, ["rev-list", f"--max-count={count + 1}", "HEAD"])
    commits = log.splitlines()
    if len(commits) < 2:
        raise SystemExit("Not enough history to compare commits.")
    return commits


def list_files(repo_dir: Path, pattern: str) -> List[str]:
    files = run_git(repo_dir, ["ls-tree", "-r", "--name-only", "HEAD"]).splitlines()
    # Use fnmatch on forward-slash paths
    import fnmatch
    return [f for f in files if fnmatch.fnmatch(f, pattern)]


def file_content_at(repo_dir: Path, commit: str, path: str) -> Optional[str]:
    try:
        return run_git(repo_dir, ["show", f"{commit}:{path}"])
    except subprocess.CalledProcessError:
        return None


def map_pair(old_text: str, new_text: str) -> List[LineMapping]:
    old_lines = [line + "\n" for line in old_text.splitlines()]
    new_lines = [line + "\n" for line in new_text.splitlines()]
    return LineMapper(old_lines, new_lines).map_lines()


def build_pairs(repo_dir: Path, commits: List[str], files: List[str], max_pairs: int, target_lines: int, seed: int) -> List[dict]:
    rng = random.Random(seed)
    rng.shuffle(files)
    dataset: List[dict] = []
    total_lines = 0
    pair_idx = 0
    for fpath in files:
        if total_lines >= target_lines or pair_idx >= max_pairs:
            break
        for i in range(len(commits) - 1):
            if total_lines >= target_lines or pair_idx >= max_pairs:
                break
            new_commit = commits[i]
            old_commit = commits[i + 1]
            new_text = file_content_at(repo_dir, new_commit, fpath)
            old_text = file_content_at(repo_dir, old_commit, fpath)
            if new_text is None or old_text is None:
                continue
            mappings = map_pair(old_text, new_text)
            remaining = target_lines - total_lines
            trimmed = mappings[:remaining]
            total_lines += len(trimmed)
            pair_idx += 1
            dataset.append(
                {
                    "pair": pair_idx,
                    "old_file": f"{fpath}@{old_commit}",
                    "new_file": f"{fpath}@{new_commit}",
                    "mappings": [{"orig": m.old_line, "new": m.new_line} for m in trimmed],
                }
            )
            if total_lines >= target_lines or pair_idx >= max_pairs:
                break
    return dataset


def copy_files_from_repo(repo_dir: Path, pairs: List[dict], dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for entry in pairs:
        old_spec = entry["old_file"]
        new_spec = entry["new_file"]
        old_path, old_commit = old_spec.split("@")
        new_path, new_commit = new_spec.split("@")
        old_content = file_content_at(repo_dir, old_commit, old_path)
        new_content = file_content_at(repo_dir, new_commit, new_path)
        if old_content is None or new_content is None:
            continue
        old_dest = dest_root / f"pair{entry['pair']}_old_{Path(old_path).name}"
        new_dest = dest_root / f"pair{entry['pair']}_new_{Path(new_path).name}"
        old_dest.write_text(old_content, encoding="utf-8")
        new_dest.write_text(new_content, encoding="utf-8")
        entry["old_file"] = str(old_dest)
        entry["new_file"] = str(new_dest)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    cloned_dir: Optional[Path] = None
    try:
        cloned_dir = clone_repo(args.repo_url, args.branch)
        commits = recent_commits(cloned_dir, args.commits)
        files = list_files(cloned_dir)
        dataset = build_pairs(cloned_dir, commits, files, args.pairs, args.target_lines, args.seed)
        if not dataset:
            raise SystemExit("No pairs generated (check commit depth and file availability).")
        if args.copy_files:
            copy_files_from_repo(cloned_dir, dataset, Path("new-test-data"))
        args.output.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
        print(f"Wrote {len(dataset)} pairs to {args.output} with total mappings capped at {args.target_lines}.")
        return 0
    finally:
        if cloned_dir and cloned_dir.exists():
            shutil.rmtree(cloned_dir, onerror=_on_rm_error)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
