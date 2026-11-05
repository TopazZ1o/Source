"""Convert pdf/docx/pptx files to Markdown with markitdown.

Usage:
    python tools/convert_to_md.py <file-or-dir> [<file-or-dir> ...] [--force]

Files located under a ``raw`` folder are written to the sibling ``md`` folder
(``lectures/raw/01.pdf`` -> ``lectures/md/01.md``). Directories are scanned
recursively. Existing up-to-date .md files are skipped unless --force is given.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from markitdown import MarkItDown

SUPPORTED = {".pdf", ".docx", ".pptx"}


def target_path(src: Path) -> Path:
    """Return the .md path for a source file (raw -> md sibling folder)."""
    parts = list(src.parent.parts)
    if "raw" in parts:
        # Replace the last 'raw' component, keep any nested sub-folders.
        idx = len(parts) - 1 - parts[::-1].index("raw")
        parts[idx] = "md"
        return Path(*parts) / (src.stem + ".md")
    return src.with_suffix(".md")


def collect(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(
                f for f in sorted(p.rglob("*"))
                if f.suffix.lower() in SUPPORTED and not f.name.startswith("~$")
            )
        elif p.suffix.lower() in SUPPORTED:
            files.append(p)
        else:
            print(f"Пропущено (неподдерживаемый формат): {p}", file=sys.stderr)
    return files


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--force", action="store_true", help="overwrite existing .md")
    args = parser.parse_args()

    converter = MarkItDown()
    failed = 0
    for src in collect(args.paths):
        dst = target_path(src)
        if dst.exists() and not args.force and dst.stat().st_mtime >= src.stat().st_mtime:
            print(f"Актуально, пропуск: {dst}")
            continue
        try:
            text = converter.convert(str(src)).text_content
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text, encoding="utf-8", newline="\n")
            print(f"OK: {src} -> {dst}")
        except Exception as exc:  # keep going on a single bad file
            failed += 1
            print(f"ОШИБКА: {src}: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
