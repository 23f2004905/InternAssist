import os
import fitz
from docx import Document as WordDocument
from docx.document import Document as _DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from pptx import Presentation


def _iter_docx_blocks(document: _DocxDocument):
    """Yield Paragraph and Table objects in document body order."""
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _extract_table_rows(table):
    """Yield formatted non-empty rows while deduplicating horizontally merged cells."""
    for row in table.rows:
        seen_cells = set()
        cell_texts = []
        for cell in row.cells:
            cell_id = id(cell._tc)
            if cell_id in seen_cells:
                continue
            seen_cells.add(cell_id)
            text = cell.text.strip()
            if text:
                cell_texts.append(text)
        if cell_texts:
            yield " | ".join(cell_texts)


def _read_text_file(file_path):
    """Read a plain text file with UTF-8 BOM support and safe fallback encodings."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with open(file_path, "r", encoding=encoding) as source:
                return source.read().strip()
        except UnicodeDecodeError:
            continue
    with open(file_path, "r", encoding="utf-8", errors="replace") as source:
        return source.read().strip()


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
        for block in _iter_docx_blocks(document):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if text:
                    parts.append(text)
            elif isinstance(block, Table):
                parts.extend(_extract_table_rows(block))
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
                    parts.extend(_extract_table_rows(shape.table))
            yield {"page_number": slide_number, "text": "\n".join(parts)}
        return

    if extension == "txt":
        yield {"page_number": 1, "text": _read_text_file(file_path)}
        return

    raise ValueError(f"Unsupported document format: {extension}")


def extract_document_pages(file_path, extension):
    """Backward-compatible list API; prefer iter_document_pages for indexing."""
    return list(iter_document_pages(file_path, extension))
