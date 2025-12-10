# comp3110

Computer Architecture II Project

## Line Mapping Tool Progress

- Added `line_mapper.py`: maps lines between old/new files using normalization, diff-anchored equals, and replace-block matching.
  - Replace blocks use a Hungarian assignment on content/context cosine similarity with weights 0.7/0.3 and a positional bonus (0.2 when the base similarity is at least 0.05), accepting matches with score â‰¥ 0.1.
  - Inserts/deletes handled via diff opcodes; blank lines are skipped for matching but line numbers reference the originals.
- Added `validate_mappings.py`: reads `test_data.json` and compares `line_mapper` output to expected mappings.
  - Current validator run still reports many mismatches; BaseTypes and asdf cases align, but larger files (e.g., ASTResolving, PluginSearchScope) remain off.
- Added `convert_test_data.py`: regenerates `test_data.json` from XML fixtures (sorted by file, versions sorted numerically).
- Tests: `test_line_mapper.py` covers small cases; `python validate_mappings.py` exercises the full dataset (currently failing many cases).

Next steps (not yet done):
- Calibrate the mapping algorithm on larger failing cases (e.g., ASTResolving, PluginSearchScope) per the LHDiff approach outlined in the provided slides.

