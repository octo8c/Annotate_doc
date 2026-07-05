from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field


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
    kind: str = "rect"  # "rect" (cadre) ou "highlight" (surlignage)
    text: str = ""  # texte du PDF sous la bbox, recupere via get_text(clip=...)
    # Pour un highlight "epouse texte" : un rectangle par ligne de mots selectionnee
    # (coordonnees PDF, points). Vide si le highlight est une zone libre (fallback).
    line_rects: list[list[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex

    def normalized(self) -> "BBox":
        x0, x1 = sorted((self.x0, self.x1))
        y0, y1 = sorted((self.y0, self.y1))
        return BBox(
            page=self.page,
            x0=x0,
            y0=y0,
            x1=x1,
            y1=y1,
            color=self.color,
            id=self.id,
            kind=self.kind,
            text=self.text,
            line_rects=self.line_rects,
        )

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
            kind=data.get("kind", "rect"),
            text=data.get("text", ""),
            line_rects=[list(rect) for rect in data.get("line_rects", [])],
        )
