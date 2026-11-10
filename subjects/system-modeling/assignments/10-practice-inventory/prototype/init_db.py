"""Creates data/inventory.db (schema + initial state). Run from the prototype folder:  python init_db.py"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from inventory.seed import build_initial_db  # noqa: E402

target = Path(__file__).resolve().parent / "data" / "inventory.db"
target.parent.mkdir(exist_ok=True)
build_initial_db(target)
print("created", target)
