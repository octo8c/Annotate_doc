from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass


@dataclass
class BBox:
    """Une annotation rectangulaire, en coordonnees PDF (points), independante du zoom d'affichage."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    color: str = "green"
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex

    def normalized(self) -> "BBox":
        x0, x1 = sorted((self.x0, self.x1))
        y0, y1 = sorted((self.y0, self.y1))
        return BBox(page=self.page, x0=x0, y0=y0, x1=x1, y1=y1, color=self.color, id=self.id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BBox":
        return cls(
            page=int(data["page"]),
            x0=float(data["x0"]),
            y0=float(data["y0"]),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
            color=data.get("color", "green"),
            id=data.get("id", ""),
        )
