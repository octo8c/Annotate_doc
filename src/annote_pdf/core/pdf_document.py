from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from PySide6.QtGui import QImage

from .models import BBox

GREEN = (0, 1, 0)


class PdfDocument:
    """Wrapper autour d'un document PyMuPDF : rendu pour l'affichage, ecriture des annotations."""

    def __init__(self) -> None:
        self._doc: fitz.Document | None = None
        self.path: Path | None = None

    def open(self, path: str | Path) -> None:
        self.path = Path(path)
        self._doc = fitz.open(self.path)

    @property
    def page_count(self) -> int:
        return self._doc.page_count if self._doc is not None else 0

    def render_page(self, page_number: int, zoom: float) -> QImage:
        if self._doc is None:
            raise RuntimeError("Aucun PDF ouvert")
        page = self._doc[page_number]
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        fmt = QImage.Format.Format_RGB888 if pix.n == 3 else QImage.Format.Format_RGBA8888
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
        return image.copy()

    def save_annotated(self, output_path: str | Path, bboxes: list[BBox], line_width: float = 1.5) -> None:
        """Dessine les bbox sur une copie fraiche du document source et sauvegarde le PDF annote."""
        if self.path is None:
            raise RuntimeError("Aucun PDF ouvert")
        doc = fitz.open(self.path)
        try:
            for bbox in bboxes:
                page = doc[bbox.page]
                rect = fitz.Rect(bbox.x0, bbox.y0, bbox.x1, bbox.y1)
                page.draw_rect(rect, color=GREEN, width=line_width)
            doc.save(str(output_path))
        finally:
            doc.close()
