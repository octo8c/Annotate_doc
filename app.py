"""Version Streamlit de Annote PDF.

Reutilise le coeur du projet original (BBox, format JSON, logique PyMuPDF),
mais remplace l'interface PySide6 par Streamlit + streamlit-drawable-canvas.

Lancement :
    streamlit run app.py

Dependances :
    pip install streamlit streamlit-drawable-canvas PyMuPDF Pillow
"""
from __future__ import annotations

import io
import json
import uuid
from dataclasses import asdict, dataclass, field

import fitz  # PyMuPDF
import streamlit as st
from PIL import Image

# --- Patch de compatibilite -------------------------------------------------
# streamlit-drawable-canvas (non maintenu) appelle streamlit.elements.image.image_to_url,
# supprime dans les versions recentes de Streamlit (deplace vers elements.lib.image_utils,
# avec une signature differente). On reinjecte un adaptateur avant d'importer st_canvas.
import streamlit.elements.image as _st_image  # noqa: E402

if not hasattr(_st_image, "image_to_url"):
    from streamlit.elements.lib.image_utils import image_to_url as _image_to_url

    try:
        from streamlit.elements.lib.layout_utils import LayoutConfig as _LayoutConfig

        def _compat_image_to_url(image, width, clamp, channels, output_format, image_id):
            return _image_to_url(
                image, _LayoutConfig(width=width), clamp, channels, output_format, image_id
            )
    except ImportError:  # versions intermediaires : ancienne signature, nouveau module

        def _compat_image_to_url(image, width, clamp, channels, output_format, image_id):
            return _image_to_url(image, width, clamp, channels, output_format, image_id)

    _st_image.image_to_url = _compat_image_to_url
# ---------------------------------------------------------------------------

from streamlit_drawable_canvas import st_canvas  # noqa: E402

GREEN = (0, 1, 0)
YELLOW = (1, 1, 0)


# ---------------------------------------------------------------------------
# Coeur (repris de src/annote_pdf/core, sans dependance Qt)
# ---------------------------------------------------------------------------

@dataclass
class BBox:
    """Une annotation rectangulaire, en coordonnees PDF (points), independante du zoom."""

    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    color: str = "green"
    id: str = ""
    kind: str = "rect"  # "rect" (cadre) ou "highlight" (surlignage)
    text: str = ""
    line_rects: list[list[float]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex

    def normalized(self) -> "BBox":
        x0, x1 = sorted((self.x0, self.x1))
        y0, y1 = sorted((self.y0, self.y1))
        return BBox(page=self.page, x0=x0, y0=y0, x1=x1, y1=y1, color=self.color,
                    id=self.id, kind=self.kind, text=self.text, line_rects=self.line_rects)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BBox":
        return cls(
            page=int(data["page"]),
            x0=float(data["x0"]), y0=float(data["y0"]),
            x1=float(data["x1"]), y1=float(data["y1"]),
            color=data.get("color", "green"),
            id=data.get("id", ""),
            kind=data.get("kind", "rect"),
            text=data.get("text", ""),
            line_rects=[list(r) for r in data.get("line_rects", [])],
        )


def render_page_png(doc: fitz.Document, page_number: int, zoom: float) -> Image.Image:
    """Rend une page en image PIL (remplace le QImage de la version Qt)."""
    page = doc[page_number]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return Image.open(io.BytesIO(pix.tobytes("png")))


def extract_text(doc: fitz.Document, page_number: int, x0, y0, x1, y1) -> str:
    page = doc[page_number]
    return page.get_text("text", clip=fitz.Rect(x0, y0, x1, y1)).strip()


def text_selection(doc: fitz.Document, page_number: int, x0, y0, x1, y1) -> tuple[str, list[list[float]]]:
    """Selection 'epouse-texte' : mots entiers touches par la zone, regroupes par ligne."""
    page = doc[page_number]
    selection = fitz.Rect(x0, y0, x1, y1)
    words = page.get_text("words")

    lines: dict[tuple[int, int], list] = {}
    for wx0, wy0, wx1, wy1, word, block_no, line_no, word_no in words:
        if fitz.Rect(wx0, wy0, wx1, wy1).intersects(selection):
            lines.setdefault((block_no, line_no), []).append((wx0, wy0, wx1, wy1, word, word_no))

    line_rects: list[list[float]] = []
    line_texts: list[str] = []
    for key in sorted(lines.keys()):
        items = sorted(lines[key], key=lambda it: it[5])
        line_rects.append([
            min(it[0] for it in items), min(it[1] for it in items),
            max(it[2] for it in items), max(it[3] for it in items),
        ])
        line_texts.append(" ".join(it[4] for it in items))
    return "\n".join(line_texts), line_rects


def save_annotated_bytes(pdf_bytes: bytes, bboxes: list[BBox], line_width: float = 1.5) -> bytes:
    """Dessine les bbox sur une copie fraiche du PDF source et retourne les bytes du PDF annote."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for bbox in bboxes:
            page = doc[bbox.page]
            rect = fitz.Rect(bbox.x0, bbox.y0, bbox.x1, bbox.y1)
            if bbox.kind == "highlight":
                if bbox.line_rects:
                    quads = [fitz.Rect(*lr).quad for lr in bbox.line_rects]
                    annot = page.add_highlight_annot(quads=quads)
                else:
                    annot = page.add_highlight_annot(rect)
                annot.set_colors(stroke=YELLOW)
                annot.update()
            else:
                page.draw_rect(rect, color=GREEN, width=line_width)
        return doc.tobytes()
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Etat de session
# ---------------------------------------------------------------------------

def init_state() -> None:
    ss = st.session_state
    ss.setdefault("pdf_bytes", None)
    ss.setdefault("pdf_name", None)
    ss.setdefault("bboxes", [])          # source de verite : toutes les pages
    ss.setdefault("page", 0)
    ss.setdefault("canvas_key", 0)       # incremente pour reinitialiser le canvas
    ss.setdefault("seen_object_count", 0)
    ss.setdefault("selected_bbox_id", None)


def get_doc() -> fitz.Document | None:
    if st.session_state.pdf_bytes is None:
        return None
    return fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")


def reset_canvas() -> None:
    st.session_state.canvas_key += 1
    st.session_state.seen_object_count = 0


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Annote PDF", layout="wide")
init_state()
ss = st.session_state

st.title("Annote PDF")

# --- Barre laterale : fichiers, mode, zoom -----------------------------------
with st.sidebar:
    st.header("Fichiers")
    pdf_file = st.file_uploader("Ouvrir un PDF", type=["pdf"])
    if pdf_file is not None and pdf_file.name != ss.pdf_name:
        ss.pdf_bytes = pdf_file.getvalue()
        ss.pdf_name = pdf_file.name
        ss.bboxes = []
        ss.page = 0
        ss.selected_bbox_id = None
        reset_canvas()

    json_file = st.file_uploader("Ouvrir des annotations (JSON)", type=["json"])
    if json_file is not None and st.button("Charger le JSON"):
        if ss.pdf_bytes is None:
            st.warning("Ouvrez d'abord un PDF.")
        else:
            raw = json.loads(json_file.getvalue().decode("utf-8"))
            ss.bboxes = [BBox.from_dict(entry) for entry in raw]
            ss.selected_bbox_id = None
            reset_canvas()
            st.success(f"{len(ss.bboxes)} annotation(s) chargee(s).")

    st.header("Outils")
    mode = st.radio("Mode de dessin", ["Rectangle", "Surligner"], horizontal=True)
    draw_kind = "highlight" if mode == "Surligner" else "rect"
    stroke_color = st.color_picker("Couleur des rectangles", "#00C800")
    zoom = st.slider("Zoom", 1.0, 3.0, 1.5, 0.25)

doc = get_doc()
if doc is None:
    st.info("Chargez un PDF dans la barre laterale pour commencer.")
    st.stop()

page_count = doc.page_count

# --- Navigation --------------------------------------------------------------
nav1, nav2, nav3, nav4 = st.columns([1, 2, 1, 6])
with nav1:
    if st.button("◀", use_container_width=True) and ss.page > 0:
        ss.page -= 1
        ss.selected_bbox_id = None
        reset_canvas()
with nav2:
    page_display = st.number_input("Page", 1, page_count, ss.page + 1, label_visibility="collapsed")
    if page_display - 1 != ss.page:
        ss.page = page_display - 1
        ss.selected_bbox_id = None
        reset_canvas()
with nav3:
    if st.button("▶", use_container_width=True) and ss.page < page_count - 1:
        ss.page += 1
        ss.selected_bbox_id = None
        reset_canvas()
with nav4:
    st.markdown(f"**Page {ss.page + 1} / {page_count}** — {ss.pdf_name}")

# --- Canvas de dessin sur la page rendue -------------------------------------
page_image = render_page_png(doc, ss.page, zoom)

# Annotations existantes de la page, pre-dessinees comme objets du canvas
initial_objects = []
for bbox in ss.bboxes:
    if bbox.page != ss.page:
        continue
    color = "#FFD700" if bbox.kind == "highlight" else stroke_color
    initial_objects.append({
        "type": "rect",
        "left": bbox.x0 * zoom,
        "top": bbox.y0 * zoom,
        "width": (bbox.x1 - bbox.x0) * zoom,
        "height": (bbox.y1 - bbox.y0) * zoom,
        "fill": "rgba(255, 215, 0, 0.3)" if bbox.kind == "highlight" else "rgba(0,0,0,0)",
        "stroke": color,
        "strokeWidth": 2,
    })

col_canvas, col_panel = st.columns([3, 1])

with col_canvas:
    canvas_result = st_canvas(
        background_image=page_image,
        drawing_mode="rect",
        stroke_color="#FFD700" if draw_kind == "highlight" else stroke_color,
        stroke_width=2,
        fill_color="rgba(255, 215, 0, 0.3)" if draw_kind == "highlight" else "rgba(0,0,0,0)",
        height=page_image.height,
        width=page_image.width,
        initial_drawing={"objects": initial_objects},
        key=f"canvas_{ss.page}_{ss.canvas_key}",
        update_streamlit=True,
    )

# Nouveaux rectangles traces : tout objet au-dela des annotations pre-chargees
if canvas_result.json_data is not None:
    objects = canvas_result.json_data.get("objects", [])
    new_objects = objects[len(initial_objects) + ss.seen_object_count:]
    for obj in new_objects:
        if obj.get("type") != "rect":
            continue
        x0 = obj["left"] / zoom
        y0 = obj["top"] / zoom
        x1 = (obj["left"] + obj["width"] * obj.get("scaleX", 1)) / zoom
        y1 = (obj["top"] + obj["height"] * obj.get("scaleY", 1)) / zoom
        bbox = BBox(page=ss.page, x0=x0, y0=y0, x1=x1, y1=y1,
                    color=stroke_color, kind=draw_kind).normalized()
        if draw_kind == "highlight":
            text, line_rects = text_selection(doc, ss.page, bbox.x0, bbox.y0, bbox.x1, bbox.y1)
            bbox.text = text
            bbox.line_rects = line_rects
        else:
            bbox.text = extract_text(doc, ss.page, bbox.x0, bbox.y0, bbox.x1, bbox.y1)
        ss.bboxes.append(bbox)
        ss.selected_bbox_id = bbox.id
    if new_objects:
        ss.seen_object_count += len(new_objects)
        st.rerun()

# --- Panneau lateral : liste + contenu de l'annotation -----------------------
with col_panel:
    st.subheader("Annotations")
    page_bboxes = [b for b in ss.bboxes if b.page == ss.page]
    if not page_bboxes:
        st.caption("Aucune annotation sur cette page. Tracez un rectangle sur le document.")
    for i, bbox in enumerate(page_bboxes):
        icon = "🟨" if bbox.kind == "highlight" else "🟩"
        label = (bbox.text or "(vide)").replace("\n", " ")[:40]
        with st.expander(f"{icon} {i + 1}. {label}", expanded=(bbox.id == ss.selected_bbox_id)):
            new_text = st.text_area("Contenu de l'annotation", bbox.text,
                                    key=f"text_{bbox.id}",
                                    placeholder="Tapez ici ce qu'il y a dans la cellule...")
            if new_text != bbox.text:
                bbox.text = new_text
            if st.button("Supprimer", key=f"del_{bbox.id}"):
                ss.bboxes = [b for b in ss.bboxes if b.id != bbox.id]
                ss.selected_bbox_id = None
                reset_canvas()
                st.rerun()

# --- Sauvegarde --------------------------------------------------------------
st.divider()
total = len(ss.bboxes)
st.markdown(f"**{total} annotation(s)** sur l'ensemble du document.")

col_a, col_b = st.columns(2)
with col_a:
    if ss.pdf_bytes is not None:
        annotated = save_annotated_bytes(ss.pdf_bytes, ss.bboxes)
        st.download_button(
            "Telecharger le PDF annote",
            data=annotated,
            file_name=(ss.pdf_name or "document").replace(".pdf", "") + "_annote.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
with col_b:
    json_payload = json.dumps([b.to_dict() for b in ss.bboxes], indent=2, ensure_ascii=False)
    st.download_button(
        "Telecharger les annotations (JSON)",
        data=json_payload.encode("utf-8"),
        file_name=(ss.pdf_name or "document").replace(".pdf", "") + "_annote.json",
        mime="application/json",
        use_container_width=True,
    )
