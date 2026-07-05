from __future__ import annotations

import json
from pathlib import Path

from .models import BBox

# Format JSON (input == output, pour permettre un recharge simple) :
# [
#   {"page": 0, "x0": 100.0, "y0": 200.0, "x1": 180.0, "y1": 240.0, "color": "green", "id": "..."},
#   ...
# ]


def load_bbox(json_path: str | Path) -> list[BBox]:
    """Charge une liste de BBox depuis un fichier JSON. Point d'extension si le format evolue."""
    path = Path(json_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [BBox.from_dict(entry) for entry in raw]


def save_bbox(json_path: str | Path, bboxes: list[BBox]) -> None:
    """Ecrit une liste de BBox vers un fichier JSON, au meme format que load_bbox attend en entree."""
    path = Path(json_path)
    raw = [bbox.to_dict() for bbox in bboxes]
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
