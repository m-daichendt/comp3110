#!/usr/bin/env python3
"""
Convert XML test data into a Python/JSON-friendly structure.

Scans `test-data` for XML descriptors, matches them to their versioned
`.java` files, normalizes mappings (using `None` for `NEW=-1`), and writes
out a consolidated JSON file at the project root.
"""

from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).parent
DATA_DIR = ROOT / "test-data"
OUTPUT = ROOT / "test_data.json"


def parse_locations(version_el: ET.Element) -> List[Dict[str, Optional[int]]]:
    """Parse <LOCATION> entries, converting NEW='-1' to None."""
    locations: List[Dict[str, Optional[int]]] = []
    for loc in version_el.findall("LOCATION"):
        orig = int(loc.attrib["ORIG"])
        new_val = int(loc.attrib["NEW"])
        locations.append({"orig": orig, "new": None if new_val == -1 else new_val})
    return locations


def version_java_path(base: str, number: int) -> Optional[str]:
    """Return relative path to the Java file for a version if it exists."""
    candidate = DATA_DIR / f"{base}_{number}.java"
    return str(candidate) if candidate.exists() else None


def parse_test_xml(xml_path: Path) -> Dict[str, Any]:
    """Convert a single XML test descriptor into a Python dictionary."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    base_name = Path(root.attrib["FILE"]).stem  # e.g., ArrayReference

    versions: List[Dict[str, Any]] = []
    for version_el in root.findall("VERSION"):
        number = int(version_el.attrib["NUMBER"])
        versions.append(
            {
                "number": number,
                "checked": version_el.attrib.get("CHECKED", "").upper() == "TRUE",
                "locations": parse_locations(version_el),
                "java_path": version_java_path(base_name, number),
            }
        )

    return {
        "file": root.attrib["FILE"],
        # ensure versions are sorted numerically
        "versions": sorted(versions, key=lambda v: v["number"]),
    }


def collect_tests() -> List[Dict[str, Any]]:
    """Parse all XML descriptors under DATA_DIR into a list of dicts."""
    tests: List[Dict[str, Any]] = []
    for xml_path in sorted(DATA_DIR.glob("*.xml")):
        if xml_path.name.endswith("~"):  # skip backup files
            continue
        tests.append(parse_test_xml(xml_path))
    # sort by target file name for deterministic output
    return sorted(tests, key=lambda t: t["file"])


def main() -> int:
    tests = collect_tests()
    OUTPUT.write_text(json.dumps(tests, indent=2), encoding="utf-8")
    print(f"Wrote {len(tests)} tests to {OUTPUT}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
