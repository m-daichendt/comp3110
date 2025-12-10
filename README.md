# comp3110

Computer Architecture II Project

## Line Mapping Tool Progress

- Added `line_mapper.py`: maps lines between old/new files using normalization, diff-anchored equals, and replace-block matching.
  - Replace blocks use a Hungarian assignment on content/context cosine similarity with weights 0.7/0.3 and a positional bonus (0.2 when the base similarity is at least 0.05), accepting matches with score >= 0.1.
  - Inserts/deletes handled via diff opcodes; blank lines are skipped for matching but line numbers reference the originals.
- Added `validate_mappings.py`: reads `test_data.json` and compares `line_mapper` output to expected mappings.
  - Current validator run still reports many mismatches; BaseTypes and asdf cases align, but larger files (e.g., ASTResolving, PluginSearchScope) remain off.
- Added `convert_test_data.py`: regenerates `test_data.json` from XML fixtures (sorted by file, versions sorted numerically).
- Tests: `test_line_mapper.py` covers small cases; `python validate_mappings.py` exercises the full dataset (currently failing many cases).

Next steps (not yet done):
- Calibrate the mapping algorithm on larger failing cases (e.g., ASTResolving, PluginSearchScope) per the LHDiff approach outlined in the provided slides.

## Validation Snapshot

- Latest run: `python validate_mappings.py` (see `validate_results.txt`)
- Status: failing with many mismatches; BaseTypes/asdf align but numerous larger cases (e.g., ASTResolving, PluginSearchScope) still differ from expected mappings.

- Latest validation log written to `validate_results.txt` by `validate_mappings.py` (current summary: 5/23 cases passed, 18 failed).

## New Dataset Tooling
- `generate_dataset.py`: build a 25-pair dataset (target ~500 mapped lines) from local files (default glob **/*.java) using the current LineMapper. Outputs `new_dataset.json`.
- `validate_new_dataset.py`: validate `new_dataset.json` against the current LineMapper to spot regressions.

## Running dataset generation against a GitHub repo
- Example (popular repo Flask):
  - `python generate_dataset.py --repo-url https://github.com/pallets/flask.git --glob "**/*.py" --pairs 25 --target-lines 500`
  - This clones the repo to a temp dir, samples 25 file pairs (Python files), caps total mapped lines at 500, and writes `new_dataset.json`.
  - After generation, run `python validate_new_dataset.py --dataset new_dataset.json` to validate against the current mapper.
- Notes: requires network access and git available locally; the temporary clone is auto-cleaned.
- `generate_dataset.py` now writes `new_test_data.json` by default and, with `--copy-files`, copies paired files into `new-test-data/` (old/new versions) for local inspection.
