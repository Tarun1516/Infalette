#!/usr/bin/env python3
"""One-off helper: add `native_enum=False, length=50` to every SAEnum
column in the Infalette models.

Alembic 001 created status / type / role / etc. columns as plain
VARCHAR(50). Python models then declared them as SAEnum(<EnumClass>),
which causes SQLAlchemy to emit ``WHERE col = $1::<enumtype>`` casts at
query time. The cast fails because the column itself isn't a Postgres
enum. The fix is to keep the SAEnum wrapper (so we still get Python
enum types at the API surface) but tell SQLAlchemy the column is
actually a varchar — `native_enum=False` does exactly that.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Pattern: SAEnum(SomeEnum)
SIMPLE_RE = re.compile(r"SAEnum\((?P<inner>[A-Z][A-Za-z0-9_]+)\)(?!\s*,\s*native_enum)")


def process(path: Path) -> bool:
    text = path.read_text()
    new = SIMPLE_RE.sub(r"SAEnum(\g<inner>, native_enum=False, length=50)", text)
    if new == text:
        return False
    path.write_text(new)
    return True


def main() -> None:
    models = ROOT / "packages/database/src/infalette_database/models"
    edited = 0
    for f in models.glob("*.py"):
        if process(f):
            edited += 1
            print(f"  edited: {f.relative_to(ROOT)}")
    print(f"Done. {edited} files edited.")


if __name__ == "__main__":
    main()
