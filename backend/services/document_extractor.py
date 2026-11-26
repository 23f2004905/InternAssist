
import fitz
import os
from docx import Document
from pptx import Presentation


def extract_pdf_pages(file_path):
    """Extract text page by page from a PDF."""

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    pages = []
    document = fitz.open(file_path)

    try:
        for page_index, page in enumerate(document):
            text = page.get_text("text").strip()

            pages.append({
                "page_number": page_index + 1,
                "text": text
            })
    finally:
        document.close()

    return pages


def extract_docx(file_path):
    """Extract DOCX paragraphs and tables with paragraph locations."""

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    document = Document(file_path)
    sections = []

    for paragraph_number, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()

        if text:
            sections.append({
                "paragraph_number": paragraph_number,
                "text": text
            })

    for table_number, table in enumerate(document.tables, start=1):
        for row_number, row in enumerate(table.rows, start=1):
            row_text = " | ".join(
                cell.text.strip() for cell in row.cells
            )

            if row_text.strip():
                sections.append({
                    "table_number": table_number,
                    "row_number": row_number,
                    "text": row_text
                })

    return sections


def extract_pptx(file_path):
    """Extract text slide by slide from PPTX."""

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    presentation = Presentation(file_path)
    slides = []

    for slide_number, slide in enumerate(presentation.slides, start=1):
        slide_text = []

        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.strip():
                slide_text.append(shape.text.strip())

            if shape.has_table:
                for row in shape.table.rows:
                    row_text = " | ".join(
                        cell.text.strip() for cell in row.cells
                    )

                    if row_text.strip():
                        slide_text.append(row_text)

        slides.append({
            "slide_number": slide_number,
            "text": "\n".join(slide_text)
        })

    return slides


def extract_txt(file_path):
    """Extract TXT content with line locations."""

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8-sig") as file:
        lines = file.readlines()

    sections = []

    for line_number, line in enumerate(lines, start=1):
        if line.strip():
            sections.append({
                "line_start": line_number,
                "line_end": line_number,
                "text": line.strip()
            })

    return sections


def extract_document(file_path, file_type):
    """Common extraction entry point for supported formats."""

    file_type = file_type.lower().lstrip(".")

    extractors = {
        "pdf": extract_pdf_pages,
        "docx": extract_docx,
        "pptx": extract_pptx,
        "txt": extract_txt
    }

    extractor = extractors.get(file_type)

    if extractor is None:
        raise ValueError(f"Unsupported file format: {file_type}")

    return extractor(file_path)
