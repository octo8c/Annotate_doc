from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QIntValidator
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QToolBar,
)

from ..core.annotation_store import load_bbox, save_bbox
from ..core.models import BBox
from ..core.pdf_document import PdfDocument
from .pdf_view import PdfView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Annote PDF")
        self.resize(1000, 800)

        self.pdf_document = PdfDocument()
        self.pdf_path: Path | None = None
        self.bboxes: list[BBox] = []  # source de verite : toutes les pages, pas seulement la page affichee

        self.pdf_view = PdfView()
        self.pdf_view.bbox_created.connect(self._on_bbox_created)
        self.pdf_view.bbox_deleted.connect(self._on_bbox_deleted)
        self.pdf_view.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self.setCentralWidget(self.pdf_view)

        self._build_toolbar()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Actions")
        self.addToolBar(toolbar)

        open_pdf_action = QAction("Ouvrir PDF", self)
        open_pdf_action.triggered.connect(self._open_pdf)
        toolbar.addAction(open_pdf_action)

        open_json_action = QAction("Ouvrir JSON", self)
        open_json_action.triggered.connect(self._open_json)
        toolbar.addAction(open_json_action)

        toolbar.addSeparator()

        color_action = QAction("Couleur", self)
        color_action.triggered.connect(self._choose_color)
        toolbar.addAction(color_action)

        toolbar.addSeparator()

        prev_action = QAction("<", self)
        prev_action.setToolTip("Page precedente (fleche gauche)")
        prev_action.triggered.connect(self._prev_page)
        toolbar.addAction(prev_action)

        self.page_input = QLineEdit()
        self.page_input.setFixedWidth(50)
        self.page_input.setPlaceholderText("Page")
        self.page_input.setValidator(QIntValidator(1, 1, self))
        self.page_input.returnPressed.connect(self._go_to_page_from_input)
        toolbar.addWidget(self.page_input)

        next_action = QAction(">", self)
        next_action.setToolTip("Page suivante (fleche droite)")
        next_action.triggered.connect(self._next_page)
        toolbar.addAction(next_action)

        toolbar.addSeparator()

        save_action = QAction("Sauvegarder", self)
        save_action.triggered.connect(self._save)
        toolbar.addAction(save_action)

        self.page_label = QLabel("")
        toolbar.addWidget(self.page_label)

    def _open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un PDF", "", "PDF (*.pdf)")
        if not path:
            return
        self.pdf_document.open(path)
        self.pdf_path = Path(path)
        self.bboxes = []
        self.pdf_view.load_document(self.pdf_document)
        self.page_input.setValidator(QIntValidator(1, max(self.pdf_document.page_count, 1), self))
        self._on_scroll_changed(0)

    def _open_json(self) -> None:
        if self.pdf_path is None:
            QMessageBox.warning(self, "Annote PDF", "Ouvrez d'abord un PDF.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir des annotations", "", "JSON (*.json)")
        if not path:
            return
        self.bboxes = load_bbox(path)
        self.pdf_view.clear_bboxes()
        self.pdf_view.load_bboxes(self.bboxes)

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self.pdf_view.pen_color, self, "Choisir la couleur des annotations")
        if color.isValid():
            self.pdf_view.set_pen_color(color)

    def _prev_page(self) -> None:
        if self.pdf_path is not None:
            self.pdf_view.scroll_to_page(self.pdf_view.current_page() - 1)

    def _next_page(self) -> None:
        if self.pdf_path is not None:
            self.pdf_view.scroll_to_page(self.pdf_view.current_page() + 1)

    def _go_to_page_from_input(self) -> None:
        if self.pdf_path is None or not self.page_input.text():
            return
        self.pdf_view.scroll_to_page(int(self.page_input.text()) - 1)

    def _on_scroll_changed(self, _value: int) -> None:
        if self.pdf_path is None:
            return
        self.page_label.setText(f"Page {self.pdf_view.current_page() + 1} / {self.pdf_document.page_count}")

    def _on_bbox_created(self, bbox: BBox) -> None:
        self.bboxes.append(bbox)

    def _on_bbox_deleted(self, bbox_id: str) -> None:
        self.bboxes = [b for b in self.bboxes if b.id != bbox_id]

    def _save(self) -> None:
        if self.pdf_path is None:
            QMessageBox.warning(self, "Annote PDF", "Ouvrez d'abord un PDF.")
            return
        pdf_out, _ = QFileDialog.getSaveFileName(self, "Sauvegarder le PDF annote", "", "PDF (*.pdf)")
        if not pdf_out:
            return
        json_out = str(Path(pdf_out).with_suffix(".json"))
        self.pdf_document.save_annotated(pdf_out, self.bboxes)
        save_bbox(json_out, self.bboxes)
        QMessageBox.information(self, "Annote PDF", f"Sauvegarde :\n{pdf_out}\n{json_out}")
