from pathlib import Path

from annote_pdf.core.annotation_store import load_bbox, save_bbox
from annote_pdf.core.models import BBox


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    bboxes = [
        BBox(page=0, x0=10.0, y0=20.0, x1=110.0, y1=80.0),
        BBox(page=1, x0=5.0, y0=5.0, x1=50.0, y1=50.0, color="green"),
    ]
    json_path = tmp_path / "annotations.json"

    save_bbox(json_path, bboxes)
    loaded = load_bbox(json_path)

    assert len(loaded) == 2
    assert loaded[0].page == 0
    assert loaded[0].x0 == 10.0
    assert loaded[0].x1 == 110.0
    assert loaded[1].id == bboxes[1].id
    assert loaded[1].color == "green"


def test_load_bbox_is_pluggable_json_shape(tmp_path: Path) -> None:
    json_path = tmp_path / "external.json"
    json_path.write_text(
        '[{"page": 2, "x0": 1, "y0": 2, "x1": 3, "y1": 4}]',
        encoding="utf-8",
    )

    loaded = load_bbox(json_path)

    assert len(loaded) == 1
    assert loaded[0].page == 2
    assert loaded[0].color == "green"
    assert loaded[0].id  # auto-genere si absent du JSON
