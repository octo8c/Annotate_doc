from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QStyle, QStyleOptionGraphicsItem, QWidget

from ..core.models import BBox

# Assez large pour rester cliquable, assez fin pour rester lisible si deux bbox sont cote a cote.
PEN_WIDTH = 3
# Transparence du remplissage pour les surlignages, pour rester lisible par-dessus le texte.
HIGHLIGHT_FILL_ALPHA = 90


class BBoxItem(QGraphicsRectItem):
    """Representation graphique (Qt) d'une BBox. Selectionnable pour permettre une suppression confirmee.

    Un highlight "epouse texte" (bbox.line_rects rempli) est dessine comme une pile de
    rectangles, un par ligne de mots selectionnee, plutot qu'un unique rectangle englobant :
    ca colle a la forme reelle du texte au lieu d'une zone libre.
    """

    def __init__(self, bbox: BBox, zoom: float, page_top: float) -> None:
        super().__init__()
        self.bbox = bbox
        self.zoom = zoom
        self.page_top = page_top
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        pen = QPen(QColor(bbox.color))
        pen.setWidth(PEN_WIDTH)
        if bbox.kind == "highlight" and bbox.line_rects:
            pen.setStyle(Qt.PenStyle.NoPen)
        self.setPen(pen)
        if bbox.kind == "highlight":
            fill_color = QColor(bbox.color)
            fill_color.setAlpha(HIGHLIGHT_FILL_ALPHA)
            self.setBrush(QBrush(fill_color))
        self._sync_geometry()

    def _sync_geometry(self) -> None:
        x0, y0 = self.bbox.x0 * self.zoom, self.page_top + self.bbox.y0 * self.zoom
        x1, y1 = self.bbox.x1 * self.zoom, self.page_top + self.bbox.y1 * self.zoom
        self.setRect(QRectF(x0, y0, x1 - x0, y1 - y0))

    def _line_rects_in_scene(self) -> list[QRectF]:
        rects = []
        for x0, y0, x1, y1 in self.bbox.line_rects:
            sx0 = x0 * self.zoom
            sy0 = self.page_top + y0 * self.zoom
            sx1 = x1 * self.zoom
            sy1 = self.page_top + y1 * self.zoom
            rects.append(QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))
        return rects

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self.bbox.kind == "highlight" and self.bbox.line_rects:
            painter.setPen(self.pen())
            painter.setBrush(self.brush())
            for rect in self._line_rects_in_scene():
                painter.drawRect(rect)
            if option.state & QStyle.StateFlag.State_Selected:
                selection_pen = QPen(QColor(self.bbox.color), 1, Qt.PenStyle.DashLine)
                painter.setPen(selection_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(self.rect())
            return
        super().paint(painter, option, widget)
