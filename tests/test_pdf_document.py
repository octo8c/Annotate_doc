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


def test_extract_text_returns_text_under_bbox(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_sample_pdf(pdf_path)

    doc = PdfDocument()
    doc.open(pdf_path)

    text = doc.extract_text(0, 0, 0, 200, 200)
    assert "Hello" in text

    empty_text = doc.extract_text(0, 150, 150, 190, 190)
    assert empty_text == ""


def test_save_annotated_writes_highlight_annotation(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_sample_pdf(pdf_path)

    doc = PdfDocument()
    doc.open(pdf_path)

    output_path = tmp_path / "highlighted.pdf"
    bbox = BBox(page=0, x0=10, y0=10, x1=100, y1=30, kind="highlight", text="Hello")
    doc.save_annotated(output_path, [bbox])

    reopened = fitz.open(output_path)
    page = reopened[0]  # garder une reference : annots() invalide sinon des que la page est GC
    annots = list(page.annots())
    assert len(annots) == 1
    assert annots[0].type[1] == "Highlight"
    reopened.close()
