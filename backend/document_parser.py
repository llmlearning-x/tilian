from pathlib import Path

from docx import Document
from pypdf import PdfReader


def extract_text(path: Path, file_type: str) -> str:
    if file_type == "pdf":
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif file_type == "docx":
        document = Document(str(path))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    else:
        text = path.read_text(encoding="utf-8")
    return text.strip()
