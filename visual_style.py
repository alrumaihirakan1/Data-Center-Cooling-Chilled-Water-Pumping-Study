"""Calibri typography and a shared plum, sage and ivory portfolio palette.

Fonts come from the user's own installation and are embedded in the PDF.
The repository does not redistribute font files. Set CALIBRI_FONT_DIR if needed.
"""
import os
from functools import lru_cache
from pathlib import Path

INK, PLUM, SAGE = "#303034", "#68455F", "#67775F"
GOLD, SLATE, MUTED = "#AC8050", "#677481", "#716C67"
LINE, PAPER, PALE, RED = "#DED8D1", "#FAF8F4", "#F1ECE5", "#9D4848"
FONT_FILES = {"regular": "calibri.ttf", "bold": "calibrib.ttf",
              "italic": "calibrii.ttf", "bold_italic": "calibriz.ttf"}


@lru_cache(maxsize=1)
def font_directory():
    configured = os.environ.get("CALIBRI_FONT_DIR")
    candidates = [Path(configured).expanduser()] if configured else [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
        Path("/Library/Fonts/Microsoft"), Path.home() / "Library/Fonts",
        Path("/usr/share/fonts/truetype/msttcorefonts"),
    ]
    for directory in candidates:
        if all((directory / name).is_file() for name in FONT_FILES.values()):
            return directory
    raise FileNotFoundError(
        "Calibri regular, bold, italic and bold italic are required for the "
        "portfolio layout. Set CALIBRI_FONT_DIR to your local Calibri folder. "
        "Use python run_project.py --data-only for the numerical study alone."
    )


def font_path(style="regular"):
    return font_directory() / FONT_FILES[style]


def register_pdf_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    names = {"regular": "Calibri", "bold": "Calibri-Bold",
             "italic": "Calibri-Italic", "bold_italic": "Calibri-BoldItalic"}
    for style, name in names.items():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_path(style))))
    pdfmetrics.registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold",
                                  italic="Calibri-Italic", boldItalic="Calibri-BoldItalic")
