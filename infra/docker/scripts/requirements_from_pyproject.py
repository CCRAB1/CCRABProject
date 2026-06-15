#!/usr/bin/env python3
"""Print runtime dependencies from one or more PEP 621 pyproject.toml files."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


def dependency_name(requirement: str) -> str:
    name = re.split(r"\s*(?:\[|@|==|!=|~=|>=|<=|>|<|;)", requirement, maxsplit=1)[0]
    return name.strip().lower().replace("_", "-")


def load_dependencies(pyproject_path: Path) -> list[str]:
    with pyproject_path.open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    return list(pyproject.get("project", {}).get("dependencies", []))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pyproject", nargs="+", type=Path)
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    excluded_names = {name.lower().replace("_", "-") for name in args.exclude}
    emitted_names: set[str] = set()

    for pyproject_path in args.pyproject:
        for dependency in load_dependencies(pyproject_path):
            name = dependency_name(dependency)
            if not name or name in excluded_names or name in emitted_names:
                continue

            print(dependency)
            emitted_names.add(name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
