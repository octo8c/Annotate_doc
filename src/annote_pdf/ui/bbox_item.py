from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

from ..core.models import BBox

# Assez large pour rester cliquable, assez fin pour rester lisible si deux bbox sont cote a cote.
PEN_WIDTH = 3


class BBoxItem(QGraphicsRectItem):
    """Representation graphique (Qt) d'une BBox. Selectionnable pour permettre une suppression confirmee."""

    def __init__(self, bbox: BBox, zoom: float, page_top: float) -> None:
        super().__init__()
        self.bbox = bbox
        self.zoom = zoom
        self.page_top = page_top
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        pen = QPen(QColor(bbox.color))
        pen.setWidth(PEN_WIDTH)
        self.setPen(pen)
        self._sync_geometry()

    def _sync_geometry(self) -> None:
        x0, y0 = self.bbox.x0 * self.zoom, self.page_top + self.bbox.y0 * self.zoom
        x1, y1 = self.bbox.x1 * self.zoom, self.page_top + self.bbox.y1 * self.zoom
        self.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))
