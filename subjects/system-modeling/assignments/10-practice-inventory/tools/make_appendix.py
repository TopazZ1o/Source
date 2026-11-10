"""Fills the marked blocks of work.md with the current content of files (code, results).

    python tools/make_appendix.py            # from the assignment folder or anywhere

Markers in work.md:
    <!-- BEGIN-FILE path -->   ... <!-- END -->    file as a code block (no syntax colouring)
    <!-- BEGIN-MD path -->     ... <!-- END -->    file inserted as Markdown

work.md stays the single source of the report; the appendix never gets out of step with the code.
"""

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work.md"
PATTERN = re.compile(r"<!-- BEGIN-(FILE|MD) (?P<path>[^ ]+) -->.*?<!-- END -->", re.S)


def render(match: re.Match) -> str:
    kind, path = match.group(1), match.group("path")
    text = (ROOT / path).read_text(encoding="utf-8").rstrip("\n")
    if kind == "MD":
        body = text
    else:
        body = f"**{path}**\n\n~~~\n{text}\n~~~"
    return f"<!-- BEGIN-{kind} {path} -->\n\n{body}\n\n<!-- END -->"


def main() -> None:
    source = WORK.read_text(encoding="utf-8")
    result, count = PATTERN.subn(render, source)
    WORK.write_text(result, encoding="utf-8")
    print(f"blocks updated: {count}")


if __name__ == "__main__":
    main()
