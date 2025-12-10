# comp3110

Computer Architecture II Project

## Line Mapping Tool Progress

- Added `line_mapper.py`: maps lines between old/new files using normalization, diff-anchored equals, and replace-block matching.
  - Replace blocks use a Hungarian assignment on content/context cosine similarity with weights 0.7/0.3 and a positional bonus (0.2 when the base similarity is at least 0.05), accepting matches with score >= 0.1.
  - Inserts/deletes handled via diff opcodes; blank lines are skipped for matching but line numbers reference the originals.
- Added `validate_mappings.py`: reads `test_data.json` and compares `line_mapper` output to expected mappings.
  - Current validator run still reports many mismatches; BaseTypes and asdf cases align, but larger files (e.g., ASTResolving, PluginSearchScope) remain off.
- Added `convert_test_data.py`: regenerates `test_data.json` from XML fixtures (sorted by file, versions sorted numerically).
- Tests: `python validate_mappings.py` exercises the full dataset (currently failing many cases).

Next steps (not yet done):
- Calibrate the mapping algorithm on larger failing cases (e.g., ASTResolving, PluginSearchScope) per the LHDiff approach outlined in the provided slides.

## Validation Snapshot

- Latest run: `python validate_mappings.py` (see `validate_results.txt`)
- Status: failing with many mismatches; BaseTypes/asdf align but numerous larger cases (e.g., ASTResolving, PluginSearchScope) still differ from expected mappings.

- Latest validation log written to `validate_results.txt` by `validate_mappings.py` (current summary: 5/23 cases passed, 18 failed).

- `generate_dataset.py`: requires `--repo-url` (GitHub repo) and compares files across recent commits (default HEAD vs HEAD~1). Produces up to 25 pairs capped at 500 mapped lines and writes `new_test_data.json`. Use `--glob` to filter files (e.g., `"**/*.py"`), `--commits` to set commit depth, and `--copy-files` to save paired versions into `new-test-data/`.
- `validate_new_dataset.py`: validates `new_test_data.json` against the current LineMapper to spot regressions and writes results to `validate_new_data_results.txt` (success or detailed failures).
- `generate_dataset.py` now writes `new_test_data.json` by default and, with `--copy-files`, copies paired files into `new-test-data/` (old/new versions) for local inspection.
- Note: when using `--repo-url`, the script now handles Windows read-only files on cleanup (`.git` packs) to avoid permission errors.
- `generate_dataset.py` now requires `--repo-url` and compares files across recent commits (default HEAD vs HEAD~1) to build `new_test_data.json`; with `--copy-files`, paired versions are saved to `new-test-data/`.

## Example Usage - microsoft/VibeVoice:

```python generate_dataset.py --repo-url https://github.com/microsoft/VibeVoice.git --glob "**/*.py" --pairs 25 --target-lines 500 --commits 1 --copy-files```
