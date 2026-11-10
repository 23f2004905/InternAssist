import os
import fitz
from docx import Document as WordDocument
from pptx import Presentation


def iter_document_pages(file_path, extension):
    """Yield extracted pages/slides one at a time to bound peak memory."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    extension = extension.lower().lstrip(".")
    if extension == "pdf":
        with fitz.open(file_path) as document:
            for page_index in range(len(document)):
                yield {"page_number": page_index + 1,
                       "text": document[page_index].get_text("text").strip()}
        return

    if extension == "docx":
        document = WordDocument(file_path)
        parts = []
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                parts.append(paragraph.text.strip())
        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                if row_text.strip(" |"):
                    parts.append(row_text)
        yield {"page_number": 1, "text": "\n".join(parts)}
        return

    if extension == "pptx":
        presentation = Presentation(file_path)
        for slide_number, slide in enumerate(presentation.slides, start=1):
            parts = []
            for shape in slide.shapes:
                if shape.has_text_frame and shape.text.strip():
                    parts.append(shape.text.strip())
                if shape.has_table:
                    for row in shape.table.rows:
                        row_text = " | ".join(cell.text.strip() for cell in row.cells)
                        if row_text.strip(" |"):
                            parts.append(row_text)
            yield {"page_number": slide_number, "text": "\n".join(parts)}
        return

    if extension == "txt":
        with open(file_path, "r", encoding="utf-8-sig") as source:
            yield {"page_number": 1, "text": source.read().strip()}
        return

    raise ValueError(f"Unsupported document format: {extension}")


def extract_document_pages(file_path, extension):
    """Backward-compatible list API; prefer iter_document_pages for indexing."""
    return list(iter_document_pages(file_path, extension))
