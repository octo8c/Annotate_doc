from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPen, QPixmap
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
    bbox_selected = Signal(object)  # BBox ou None (aucune selection / plusieurs a la fois)

    def __init__(self) -> None:
        super().__init__()
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.setBackgroundBrush(BACKGROUND_COLOR)
        self.zoom = 2.0
        self.pen_color = QColor("green")
        self.draw_mode = "rect"  # "rect" ou "highlight"
        self._pdf_document: PdfDocument | None = None
        self._page_tops: list[float] = []
        self._page_heights: list[float] = []
        self._bbox_items: list[BBoxItem] = []
        self._drag_start = None
        self._drag_page: int | None = None
        self._drag_rect_item: QGraphicsRectItem | None = None
        self.scene_.selectionChanged.connect(self._on_selection_changed)

    @property
    def page_count(self) -> int:
        return len(self._page_tops)

    def set_pen_color(self, color: QColor) -> None:
        self.pen_color = color

    def set_draw_mode(self, mode: str) -> None:
        self.draw_mode = mode

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
        self._pdf_document = pdf_document
        self.scene_.clearSelection()
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
        self.scene_.clearSelection()
        for item in self._bbox_items:
            self.scene_.removeItem(item)
        self._bbox_items = []

    def _on_selection_changed(self) -> None:
        selected = [item for item in self.scene_.selectedItems() if isinstance(item, BBoxItem)]
        self.bbox_selected.emit(selected[0].bbox if len(selected) == 1 else None)

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
            if not isinstance(item_under, BBoxItem):
                # Clic en dehors d'une annotation existante : on desactive la selection
                # courante (et donc le champ de contenu associe dans le panneau lateral).
                self.scene_.clearSelection()
            if page is not None and not isinstance(item_under, BBoxItem):
                self._drag_start = scene_pos
                self._drag_page = page
                pen = QPen(self.pen_color, 2)
                brush = Qt.BrushStyle.NoBrush
                if self.draw_mode == "highlight":
                    fill_color = QColor(self.pen_color)
                    fill_color.setAlpha(90)
                    brush = QBrush(fill_color)
                self._drag_rect_item = self.scene_.addRect(QRectF(scene_pos, scene_pos), pen, brush)
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
                x0 = rect.left() / self.zoom
                y0 = (rect.top() - page_top) / self.zoom
                x1 = rect.right() / self.zoom
                y1 = (rect.bottom() - page_top) / self.zoom
                text = ""
                line_rects: list[list[float]] = []
                if self._pdf_document is not None:
                    if self.draw_mode == "highlight":
                        text, line_rects = self._pdf_document.text_selection(page, x0, y0, x1, y1)
                        if line_rects:
                            # La bbox englobe les mots reellement selectionnes, pas le
                            # rectangle libre trace a la souris.
                            x0 = min(r[0] for r in line_rects)
                            y0 = min(r[1] for r in line_rects)
                            x1 = max(r[2] for r in line_rects)
                            y1 = max(r[3] for r in line_rects)
                    else:
                        text = self._pdf_document.extract_text(page, x0, y0, x1, y1)
                bbox = BBox(
                    page=page,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    color=self.pen_color.name(),
                    kind=self.draw_mode,
                    text=text,
                    line_rects=line_rects,
                )
                item = BBoxItem(bbox, self.zoom, page_top)
                self.scene_.addItem(item)
                self._bbox_items.append(item)
                self.bbox_created.emit(bbox)
                # Selectionne immediatement la nouvelle bbox pour que le champ de saisie
                # du contenu apparaisse tout de suite dans le panneau lateral.
                item.setSelected(True)
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
        if selected:
            # removeItem() ne declenche pas toujours selectionChanged : on force la mise
            # a jour du panneau lateral pour qu'il se ferme.
            self._on_selection_changed()
