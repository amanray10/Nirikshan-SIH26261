"""PDF/image parsing: digital text with coordinates, OCR for scanned pages, page rendering for the evidence viewer."""
import io
from pathlib import Path

import pymupdf
from PIL import Image

from .ocr import ocr_image
from .types import Line, PageText

IMAGE_EXT = {".jpg", ".jpeg", ".png"}
OCR_DPI = 200


def is_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXT


def page_count(path: str | Path) -> int:
    if is_image(path):
        return 1
    with pymupdf.open(path) as doc:
        return doc.page_count


def _digital_lines(page: pymupdf.Page) -> list[Line]:
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for ln in block.get("lines", []):
            text = "".join(span["text"] for span in ln["spans"]).strip()
            if text:
                lines.append(Line(text, [round(v, 1) for v in ln["bbox"]], 1.0))
    lines.sort(key=lambda l: (round(l.bbox[1]), l.bbox[0]))
    return _merge_same_row(lines)


def _merge_same_row(lines: list[Line]) -> list[Line]:
    """Join fragments on the same baseline ("Survey No.:" + "123/4A") so label/value regexes work."""
    merged: list[Line] = []
    for ln in lines:
        if merged:
            prev = merged[-1]
            same_row = abs(prev.bbox[1] - ln.bbox[1]) < 3 and abs(prev.bbox[3] - ln.bbox[3]) < 3
            gap = ln.bbox[0] - prev.bbox[2]
            if same_row and 0 <= gap < 260:
                prev.text = f"{prev.text} {ln.text}"
                prev.bbox = [min(prev.bbox[0], ln.bbox[0]), min(prev.bbox[1], ln.bbox[1]),
                             max(prev.bbox[2], ln.bbox[2]), max(prev.bbox[3], ln.bbox[3])]
                continue
        merged.append(Line(ln.text, list(ln.bbox), ln.conf))
    return merged


def extract_pages(path: str | Path) -> list[PageText]:
    """Digital text where available; OCR for pages that are images."""
    path = Path(path)
    if is_image(path):
        with Image.open(path) as im:
            return [PageText(1, im.width, im.height, [], "image")]
    pages = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            lines = _digital_lines(page)
            if sum(len(l.text) for l in lines) >= 25:
                pages.append(PageText(i, page.rect.width, page.rect.height, lines, "digital"))
                continue
            if page.get_images():
                scale = OCR_DPI / 72
                pix = page.get_pixmap(dpi=OCR_DPI)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                ocr_lines, src = ocr_image(img, scale)
                pages.append(PageText(i, page.rect.width, page.rect.height, ocr_lines, src))
            else:
                pages.append(PageText(i, page.rect.width, page.rect.height, lines, "empty"))
    return pages


def render_page_png(path: str | Path, page_no: int, dpi: int = 110) -> tuple[bytes, float, float]:
    """PNG bytes plus the page size in PDF points (the coordinate space of every bbox)."""
    path = Path(path)
    if is_image(path):
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            im.thumbnail((1400, 1400))
            buf = io.BytesIO()
            im.save(buf, "PNG")
            return buf.getvalue(), float(w), float(h)
    with pymupdf.open(path) as doc:
        page = doc[page_no - 1]
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png"), page.rect.width, page.rect.height


def page_images(path: str | Path, dpi: int = 150) -> list[tuple[int, Image.Image, float]]:
    """(page_no, PIL image, scale px-per-point) for forensic checks."""
    path = Path(path)
    if is_image(path):
        im = Image.open(path)
        im.load()
        return [(1, im, 1.0)]
    out = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi)
            out.append((i, Image.open(io.BytesIO(pix.tobytes("png"))), dpi / 72))
    return out


def embedded_rasters(path: str | Path) -> list[tuple[int, Image.Image, list[float], float]]:
    """Large raster images inside PDF pages (scans/photos): (page, image, bbox_pts, px_per_pt)."""
    path = Path(path)
    if is_image(path):
        im = Image.open(path)
        im.load()
        return [(1, im, [0, 0, im.width, im.height], 1.0)]
    out = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            for info in page.get_images(full=True):
                xref = info[0]
                rects = page.get_image_rects(xref)
                if not rects:
                    continue
                rect = rects[0]
                if rect.width * rect.height < 0.08 * page.rect.width * page.rect.height:
                    continue
                raw = doc.extract_image(xref)
                im = Image.open(io.BytesIO(raw["image"]))
                im.load()
                out.append((i, im, [rect.x0, rect.y0, rect.x1, rect.y1], im.width / rect.width))
    return out
