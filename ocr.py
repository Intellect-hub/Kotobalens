"""Japanese subtitle OCR using bundled Tesseract when available."""

import os
import sys
import time
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps, ImageEnhance


def _configure_tesseract():
    """Prefer bundled OCR files, with system installation as fallback."""
    if getattr(sys, "frozen", False):
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base_dir = Path(__file__).resolve().parent

    candidates = [
        base_dir / "tesseract" / "tesseract.exe",
        Path(sys.executable).resolve().parent / "tesseract" / "tesseract.exe",
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    ]
    for executable in candidates:
        if executable.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(executable)
            tessdata = executable.parent / "tessdata"
            if tessdata.is_dir():
                os.environ["TESSDATA_PREFIX"] = str(tessdata)
            return

    # Let pytesseract search PATH if no known location exists.
    pytesseract.pytesseract.tesseract_cmd = "tesseract"


_configure_tesseract()


def recognize_japanese(image_path):
    total_start = time.perf_counter()

    start = time.perf_counter()
    image = Image.open(image_path).convert("RGB")
    print(f"Image loading: {time.perf_counter() - start:.3f}s")

    start = time.perf_counter()
    image = image.resize(
        (image.width * 3, image.height * 3),
        Image.Resampling.LANCZOS,
    )
    print(f"Image resizing: {time.perf_counter() - start:.3f}s")

    start = time.perf_counter()
    image = ImageEnhance.Contrast(image).enhance(1.5)
    image = ImageOps.grayscale(image)
    print(f"Image enhancement: {time.perf_counter() - start:.3f}s")

    start = time.perf_counter()
    text = pytesseract.image_to_string(image, lang="jpn", config="--psm 6")
    print(f"Tesseract OCR: {time.perf_counter() - start:.3f}s")
    print(f"TOTAL OCR TIME: {time.perf_counter() - total_start:.3f}s")
    return text.strip()
