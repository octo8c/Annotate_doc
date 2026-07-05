from pathlib import Path

import fitz

from annote_pdf.core.models import BBox
from annote_pdf.core.pdf_document import PdfDocument


def _make_sample_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((20, 20), "Hello")
    doc.save(path)
    doc.close()


def test_render_and_save_annotated(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_sample_pdf(pdf_path)

    doc = PdfDocument()
    doc.open(pdf_path)
    assert doc.page_count == 1

    image = doc.render_page(0, zoom=1.0)
    assert image.width() > 0
    assert image.height() > 0

    output_path = tmp_path / "annotated.pdf"
    bbox = BBox(page=0, x0=10, y0=10, x1=100, y1=100)
    doc.save_annotated(output_path, [bbox])

    assert output_path.exists()

    # le document source reste inchange sur disque : uniquement la copie de sortie est annotee
    reopened = fitz.open(pdf_path)
    assert len(reopened[0].get_drawings()) == 0
    reopened.close()
