from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from PySide6.QtGui import QImage

from .models import BBox

GREEN = (0, 1, 0)
YELLOW = (1, 1, 0)


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

    def extract_text(self, page_number: int, x0: float, y0: float, x1: float, y1: float) -> str:
        """Recupere le texte du PDF sous une bbox (coordonnees PDF, points), via get_text(clip=...)."""
        if self._doc is None:
            raise RuntimeError("Aucun PDF ouvert")
        page = self._doc[page_number]
        clip = fitz.Rect(x0, y0, x1, y1)
        return page.get_text("text", clip=clip).strip()

    def text_selection(
        self, page_number: int, x0: float, y0: float, x1: float, y1: float
    ) -> tuple[str, list[list[float]]]:
        """Trouve les mots du PDF touches par une zone glissee et les regroupe par ligne.

        Contrairement a extract_text(clip=...), qui coupe les mots au milieu des qu'ils
        depassent la zone, ceci garde les mots entiers (comme une selection de texte dans
        un lecteur PDF) : un mot est inclus des que sa bbox touche la zone selectionnee.
        Retourne (texte, rectangles par ligne) ; rectangles vide si aucun mot touche.
        """
        if self._doc is None:
            raise RuntimeError("Aucun PDF ouvert")
        page = self._doc[page_number]
        selection = fitz.Rect(x0, y0, x1, y1)
        words = page.get_text("words")

        lines: dict[tuple[int, int], list[tuple[float, float, float, float, str, int]]] = {}
        for wx0, wy0, wx1, wy1, word, block_no, line_no, word_no in words:
            if fitz.Rect(wx0, wy0, wx1, wy1).intersects(selection):
                key = (block_no, line_no)
                lines.setdefault(key, []).append((wx0, wy0, wx1, wy1, word, word_no))

        line_rects: list[list[float]] = []
        line_texts: list[str] = []
        for key in sorted(lines.keys()):
            items = sorted(lines[key], key=lambda item: item[5])
            line_rects.append(
                [
                    min(item[0] for item in items),
                    min(item[1] for item in items),
                    max(item[2] for item in items),
                    max(item[3] for item in items),
                ]
            )
            line_texts.append(" ".join(item[4] for item in items))

        return "\n".join(line_texts), line_rects

    def save_annotated(self, output_path: str | Path, bboxes: list[BBox], line_width: float = 1.5) -> None:
        """Dessine les bbox sur une copie fraiche du document source et sauvegarde le PDF annote."""
        if self.path is None:
            raise RuntimeError("Aucun PDF ouvert")
        doc = fitz.open(self.path)
        try:
            for bbox in bboxes:
                page = doc[bbox.page]
                rect = fitz.Rect(bbox.x0, bbox.y0, bbox.x1, bbox.y1)
                if bbox.kind == "highlight":
                    if bbox.line_rects:
                        quads = [fitz.Rect(*line_rect).quad for line_rect in bbox.line_rects]
                        annot = page.add_highlight_annot(quads=quads)
                    else:
                        annot = page.add_highlight_annot(rect)
                    annot.set_colors(stroke=YELLOW)
                    annot.update()
                else:
                    page.draw_rect(rect, color=GREEN, width=line_width)
            doc.save(str(output_path))
        finally:
            doc.close()
