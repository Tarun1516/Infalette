#!/usr/bin/env python3
"""Replace alert(...) calls in TypeScript/TSX files with toast(...) calls.

This script is one-off: it edits .ts/.tsx files under apps/{admin,storefront,platform-admin}
that still contain `alert(...)` so the user-facing notification is a
toast (small floating dialog) instead of a blocking browser alert.

Patterns handled:
  - alert("some string")
  - alert(someVar)
  - alert(e.message || "Fallback")
  - alert("Lead converted to customer")
  - alert("text " + (x || "default"))

For each match we emit a `toast({ kind: "error"|"success"|"info", title: ..., description?: ... })`
call that uses the appropriate Toaster component from the same app.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APPS = [
    ("apps/admin", "admin"),
    ("apps/storefront", "storefront"),
    ("apps/platform-admin", "platform-admin"),
]

# Files we will NOT touch — they're in node_modules / .next / build artifacts
EXCLUDE_DIRS = {"node_modules", ".next", "__pycache__", "dist", "build"}


def is_message_only(expr: str) -> bool:
    """Return True when the expression is a plain string literal or a single
    variable / dotted member access. Used to pick the right toast shape."""
    e = expr.strip()
    if not e:
        return True
    # Pure string literal
    if (e.startswith('"') and e.endswith('"')) or (e.startswith("'") and e.endswith("'")) or (e.startswith("`") and e.endswith("`")):
        return True
    # Member access like e.message, err.message, error
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(\.[A-Za-z_$][A-Za-z0-9_$]*)*", e):
        return True
    return False


def is_string_literal(expr: str) -> tuple[bool, str]:
    e = expr.strip()
    if (e.startswith('"') and e.endswith('"')) or (e.startswith("'") and e.endswith("'")) or (e.startswith("`") and e.endswith("`")):
        return True, e[1:-1]
    return False, ""


def to_kind_and_title(expr: str) -> tuple[str, str, str | None]:
    """Convert an alert(...) expression into a toast({...}) call.

    Returns (kind, title_literal, description_expression_or_None).
    Heuristics:
      - Pure string → use as title.
      - Single variable → use as description with a generic title.
      - Anything else (e.g. `e.message || "..."`) → keep as description.
    """
    expr = expr.strip()
    is_lit, lit = is_string_literal(expr)
    if is_lit:
        # Detect positive/negative wording for kind
        low = lit.lower()
        kind = "info"
        if any(w in low for w in ("failed", "error", "couldn", "unable", "invalid", "forbidden", "denied", "not ", "expired")):
            kind = "error"
        elif any(w in low for w in ("success", "saved", "created", "deleted", "updated", "sent", "assigned", "closed", "imported", "exported", "converted", "published", "uploaded", "applied", "converted", "scheduled")):
            kind = "success"
        return kind, lit, None
    if is_message_only(expr):
        # Variable like e.message or err
        return "error", "Something went wrong", expr
    # Composite: keep original as description
    return "error", "Something went wrong", expr


def build_toast(expr: str) -> str:
    kind, title, desc = to_kind_and_title(expr)
    parts = [f'kind: "{kind}"', f"title: {json_encode(title) if desc is None else json_encode(title)}"]
    if desc is not None:
        parts.append(f"description: {desc}")
    return "toast({ " + ", ".join(parts) + " })"


def json_encode(s: str) -> str:
    """Return a JS-style string literal for a Python str."""
    return json.dumps(s, ensure_ascii=False)


import json

# Improved: build_toast uses json.dumps above; keep helper for clarity.
def build_toast_call(expr: str) -> str:
    kind, title, desc = to_kind_and_title(expr)
    title_js = json.dumps(title, ensure_ascii=False)
    if desc is None:
        return f"toast({{ kind: {json.dumps(kind)}, title: {title_js} }})"
    return f"toast({{ kind: {json.dumps(kind)}, title: {title_js}, description: {desc} }})"


ALERT_RE = re.compile(r"alert\((?P<expr>.*?)\);?", re.DOTALL)


def process_file(path: Path, app: str) -> bool:
    text = path.read_text()
    if "alert(" not in text:
        return False

    # Skip if there's no obvious import line to add
    needs_import = "import" not in text.splitlines()[0:30].__str__() or "toaster" not in text

    new_text = ALERT_RE.sub(lambda m: build_toast_call(m.group("expr")) + ";" if m.group(0).endswith(";") else build_toast_call(m.group("expr")), text)

    if new_text == text:
        return False

    if needs_import:
        # Try to insert the toaster import at the top of the file
        import_line = f'import {{ toast }} from "@/components/toaster";\n'
        # Find the first import line
        lines = new_text.splitlines(keepends=True)
        inserted = False
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("import ") or stripped.startswith('"use client"'):
                # If it's "use client" we want to add the import after it
                if stripped.startswith('"use client"'):
                    if i + 1 < len(lines) and lines[i + 1].startswith("\n"):
                        lines.insert(i + 1, "\n" + import_line)
                    else:
                        lines.insert(i + 1, import_line)
                    inserted = True
                    break
                else:
                    lines.insert(i, import_line)
                    inserted = True
                    break
        if not inserted:
            new_text = import_line + new_text
        else:
            new_text = "".join(lines)

    path.write_text(new_text)
    return True


def main() -> None:
    edited = 0
    for app_dir, app in APPS:
        for ts in (ROOT / app_dir).rglob("*.tsx"):
            if any(ex in ts.parts for ex in EXCLUDE_DIRS):
                continue
            if process_file(ts, app):
                edited += 1
                print(f"  edited: {ts.relative_to(ROOT)}")
        for ts in (ROOT / app_dir).rglob("*.ts"):
            if any(ex in ts.parts for ex in EXCLUDE_DIRS):
                continue
            if process_file(ts, app):
                edited += 1
                print(f"  edited: {ts.relative_to(ROOT)}")
    print(f"Done. {edited} files edited.")


if __name__ == "__main__":
    main()
