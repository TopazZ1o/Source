"""Builds all UML diagrams of the report: kolesa-style single .drawio file + PNG per page.

Run from the tools directory (Python 3.11 with Pillow):
    python build_diagrams.py [page numbers]      e.g. python build_diagrams.py 1 2

Output: ../aircraft_maintenance_oo_model.drawio (one page per diagram) and ../assets/NN_name.png.
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from diagram_lib import drawio_file  # noqa: E402
import diagrams_a  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent
PAGES = [
    ("01_use_case", diagrams_a.d01_use_case),
    ("02_conceptual_model", diagrams_a.d02_conceptual),
    ("03_design_classes_domain", diagrams_a.d03_design_domain),
    ("04_design_classes_services", diagrams_a.d04_design_services),
]
try:
    import diagrams_b
    PAGES += [("05_sequence_request", diagrams_b.d05_sequence_request),
              ("06_sequence_assign", diagrams_b.d06_sequence_assign),
              ("07_sequence_release", diagrams_b.d07_sequence_release)]
except ImportError:
    pass
try:
    import diagrams_c
    PAGES += [("08_activity", diagrams_c.d08_activity), ("09_state_machine", diagrams_c.d09_state_aircraft),
              ("10_object", diagrams_c.d10_object), ("11_state_request_v2", diagrams_c.d11_state_request_v2)]
except ImportError:
    pass


def main(selected):
    (OUT / "assets").mkdir(exist_ok=True)
    canvases = []
    for i, (name, fn) in enumerate(PAGES, 1):
        canvas = fn()
        canvases.append(canvas)
        if not selected or i in selected:
            canvas.to_png(str(OUT / "assets" / f"{name}.png"))
            print("png", name, canvas.w, "x", canvas.h)
    (OUT / "aircraft_maintenance_oo_model.drawio").write_text(drawio_file(canvases), encoding="utf-8")
    print("drawio pages:", len(canvases))


if __name__ == "__main__":
    main({int(a) for a in sys.argv[1:]})
