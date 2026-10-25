"""OCR with graceful fallback: PaddleOCR (best for Devanagari) -> Tesseract -> none.

OCR confidence says how sure the engine is about the characters, not whether the fact is true.
"""
import functools
import shutil

from PIL import Image

from ..config import settings
from .types import Line


@functools.lru_cache(maxsize=1)
def available_engine() -> str:
    pref = settings.ocr_backend
    if pref in ("auto", "paddle"):
        try:
            import paddleocr  # noqa: F401
            return "paddle"
        except Exception:
            if pref == "paddle":
                return "none"
    if pref in ("auto", "tesseract"):
        try:
            import os
            import pytesseract
            cmd = settings.tesseract_cmd
            win_default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if not cmd and os.name == "nt" and os.path.exists(win_default):
                cmd = win_default  # standard Windows installer location
            if cmd:
                pytesseract.pytesseract.tesseract_cmd = cmd
            if cmd or shutil.which("tesseract"):
                pytesseract.get_tesseract_version()
                return "tesseract"
        except Exception:
            pass
    return "none"


@functools.lru_cache(maxsize=1)
def _paddle():
    from paddleocr import PaddleOCR
    # 'devanagari' model reads Hindi/Marathi plus Latin digits; 'en' for English-only docs.
    return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)


def _tesseract_langs() -> str:
    import pytesseract
    try:
        langs = set(pytesseract.get_languages(config=""))
    except Exception:
        langs = {"eng"}
    use = [l for l in ("eng", "hin", "mar") if l in langs]
    return "+".join(use) or "eng"


def ocr_image(img: Image.Image, scale: float) -> tuple[list[Line], str]:
    """Return lines with bboxes in PDF points (pixel coords / scale)."""
    engine = available_engine()
    if engine == "paddle":
        import numpy as np
        result = _paddle().ocr(np.array(img.convert("RGB")), cls=True) or []
        lines = []
        for page in result:
            for box, (text, conf) in page or []:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                lines.append(Line(text, [min(xs) / scale, min(ys) / scale, max(xs) / scale, max(ys) / scale], float(conf)))
        lines.sort(key=lambda l: (round(l.bbox[1] / 4), l.bbox[0]))
        return lines, "ocr:paddle"
    if engine == "tesseract":
        import pytesseract
        data = pytesseract.image_to_data(img.convert("L"), lang=_tesseract_langs(),
                                         config="--psm 4", output_type=pytesseract.Output.DICT)
        groups: dict[tuple, list[int]] = {}
        for i, word in enumerate(data["text"]):
            if word.strip() and float(data["conf"][i]) >= 0:
                groups.setdefault((data["block_num"][i], data["par_num"][i], data["line_num"][i]), []).append(i)
        lines = []
        for idxs in groups.values():
            words = [data["text"][i] for i in idxs]
            x0 = min(data["left"][i] for i in idxs)
            y0 = min(data["top"][i] for i in idxs)
            x1 = max(data["left"][i] + data["width"][i] for i in idxs)
            y1 = max(data["top"][i] + data["height"][i] for i in idxs)
            conf = sum(float(data["conf"][i]) for i in idxs) / len(idxs) / 100.0
            lines.append(Line(" ".join(words), [x0 / scale, y0 / scale, x1 / scale, y1 / scale], round(conf, 3)))
        lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
        return lines, "ocr:tesseract"
    return [], "ocr:none"
