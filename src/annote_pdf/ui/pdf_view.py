from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView

from ..core.models import BBox
from ..core.pdf_document import PdfDocument
from .bbox_item import BBoxItem

# En dessous de ce seuil (en pixels ecran), on considere que c'est un clic accidentel, pas un vrai drag.
MIN_DRAG_PIXELS = 4
# Espace entre deux pages empilees, pour bien les distinguer en defilement continu.
PAGE_GAP = 16
BACKGROUND_COLOR = QColor(43, 43, 43)


class PdfView(QGraphicsView):
    """Affiche toutes les pages d'un PDF empilees verticalement (defilement continu, comme un lecteur PDF).

    Cree une bbox par clic-glisser, la supprime par selection + touche Suppr.
    """

    bbox_created = Signal(object)  # BBox
    bbox_deleted = Signal(str)  # bbox.id

    def __init__(self) -> None:
        super().__init__()
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.setBackgroundBrush(BACKGROUND_COLOR)
        self.zoom = 2.0
        self.pen_color = QColor("green")
        self._page_tops: list[float] = []
        self._page_heights: list[float] = []
        self._bbox_items: list[BBoxItem] = []
        self._drag_start = None
        self._drag_page: int | None = None
        self._drag_rect_item: QGraphicsRectItem | None = None

    @property
    def page_count(self) -> int:
        return len(self._page_tops)

    def set_pen_color(self, color: QColor) -> None:
        self.pen_color = color

    def current_page(self) -> int:
        """Page dont le haut est visible en haut du viewport (utilisee pour la navigation par page)."""
        if not self._page_tops:
            return 0
        top_y = self.mapToScene(self.viewport().rect().topLeft()).y()
        page = 0
        for index, top in enumerate(self._page_tops):
            if top <= top_y + 1:
                page = index
            else:
                break
        return page

    def scroll_to_page(self, index: int) -> None:
        if not self._page_tops:
            return
        index = max(0, min(index, len(self._page_tops) - 1))
        self.verticalScrollBar().setValue(int(self._page_tops[index]))

    def load_document(self, pdf_document: PdfDocument) -> None:
        self.scene_.clear()
        self._bbox_items = []
        self._page_tops = []
        self._page_heights = []

        y = 0.0
        max_width = 0.0
        for page_number in range(pdf_document.page_count):
            image = pdf_document.render_page(page_number, self.zoom)
            pixmap = QPixmap.fromImage(image)
            item = self.scene_.addPixmap(pixmap)
            item.setPos(0, y)
            self._page_tops.append(y)
            self._page_heights.append(float(pixmap.height()))
            max_width = max(max_width, float(pixmap.width()))
            y += pixmap.height() + PAGE_GAP

        self.scene_.setSceneRect(QRectF(0, 0, max_width, max(y - PAGE_GAP, 0)))

    def clear_bboxes(self) -> None:
        for item in self._bbox_items:
            self.scene_.removeItem(item)
        self._bbox_items = []

    def load_bboxes(self, bboxes: list[BBox]) -> None:
        for bbox in bboxes:
            if bbox.page >= len(self._page_tops):
                continue
            item = BBoxItem(bbox, self.zoom, self._page_tops[bbox.page])
            self.scene_.addItem(item)
            self._bbox_items.append(item)

    def _page_at_scene_y(self, y: float) -> int | None:
        for index, (top, height) in enumerate(zip(self._page_tops, self._page_heights)):
            if top <= y <= top + height:
                return index
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            page = self._page_at_scene_y(scene_pos.y())
            item_under = self.itemAt(event.pos())
            if page is not None and not isinstance(item_under, BBoxItem):
                self._drag_start = scene_pos
                self._drag_page = page
                self._drag_rect_item = self.scene_.addRect(
                    QRectF(scene_pos, scene_pos), QPen(self.pen_color, 2)
                )
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None and self._drag_rect_item is not None and self._drag_page is not None:
            current = self.mapToScene(event.pos())
            top = self._page_tops[self._drag_page]
            height = self._page_heights[self._drag_page]
            current.setY(min(max(current.y(), top), top + height))
            self._drag_rect_item.setRect(QRectF(self._drag_start, current).normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None and self._drag_rect_item is not None and self._drag_page is not None:
            rect = self._drag_rect_item.rect()
            page = self._drag_page
            page_top = self._page_tops[page]
            self.scene_.removeItem(self._drag_rect_item)
            self._drag_rect_item = None
            self._drag_start = None
            self._drag_page = None

            if rect.width() >= MIN_DRAG_PIXELS and rect.height() >= MIN_DRAG_PIXELS:
                bbox = BBox(
                    page=page,
                    x0=rect.left() / self.zoom,
                    y0=(rect.top() - page_top) / self.zoom,
                    x1=rect.right() / self.zoom,
                    y1=(rect.bottom() - page_top) / self.zoom,
                    color=self.pen_color.name(),
                )
                item = BBoxItem(bbox, self.zoom, page_top)
                self.scene_.addItem(item)
                self._bbox_items.append(item)
                self.bbox_created.emit(bbox)
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._delete_selected()
            return
        if event.key() == Qt.Key.Key_Right:
            self.scroll_to_page(self.current_page() + 1)
            return
        if event.key() == Qt.Key.Key_Left:
            self.scroll_to_page(self.current_page() - 1)
            return
        super().keyPressEvent(event)

    def _delete_selected(self) -> None:
        selected = [item for item in self._bbox_items if item.isSelected()]
        for item in selected:
            self.scene_.removeItem(item)
            self._bbox_items.remove(item)
            self.bbox_deleted.emit(item.bbox.id)
