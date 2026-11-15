import os
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import fitz
from docx import Document
from pptx import Presentation


class DocumentExtractionError(ValueError):
    pass


def extract_pdf_pages(file_path):
    """
    Extract text from a PDF page-by-page.

    Returns:
        [
            {
                "page_number": 1,
                "text": "..."
            },
            ...
        ]
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    pages = []

    document = fitz.open(file_path)

    try:

        for page_index in range(
            len(document)
        ):

            page = document[
                page_index
            ]

            text = page.get_text(
                "text"
            ).strip()

            pages.append({
                "page_number": page_index + 1,
                "text": text
            })

    finally:

        document.close()

    return pages


def _validate_zip_office_file(file_path, expected_directory):
    try:
        with ZipFile(file_path) as archive:
            names = set(archive.namelist())
    except (BadZipFile, OSError) as error:
        raise DocumentExtractionError("The uploaded Office document is malformed.") from error

    if "[Content_Types].xml" not in names or not any(
        name.startswith(f"{expected_directory}/") for name in names
    ):
        raise DocumentExtractionError("The file contents do not match its extension.")


def validate_document(file_path, extension):
    extension = extension.lower()
    if extension == "pdf":
        with open(file_path, "rb") as uploaded_file:
            if uploaded_file.read(5) != b"%PDF-":
                raise DocumentExtractionError("The file contents are not a valid PDF.")
    elif extension == "docx":
        _validate_zip_office_file(file_path, "word")
    elif extension == "pptx":
        _validate_zip_office_file(file_path, "ppt")
    elif extension == "txt":
        raw = Path(file_path).read_bytes()
        if b"\x00" in raw:
            raise DocumentExtractionError("The uploaded TXT file appears to be binary.")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DocumentExtractionError("TXT documents must use UTF-8 encoding.") from error
    else:
        raise DocumentExtractionError("This file type is not supported.")


def extract_document_pages(file_path, extension):
    validate_document(file_path, extension)
    extension = extension.lower()

    try:
        if extension == "pdf":
            pages = extract_pdf_pages(file_path)
        elif extension == "docx":
            document = Document(file_path)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs if paragraph.text.strip())
            pages = [{"page_number": None, "text": text}]
        elif extension == "pptx":
            presentation = Presentation(file_path)
            pages = []
            for slide_number, slide in enumerate(presentation.slides, start=1):
                text = "\n".join(
                    shape.text for shape in slide.shapes
                    if hasattr(shape, "text") and shape.text.strip()
                )
                pages.append({"page_number": slide_number, "text": text})
        else:
            pages = [{"page_number": None, "text": Path(file_path).read_text(encoding="utf-8")}]
    except (DocumentExtractionError, FileNotFoundError):
        raise
    except Exception as error:
        raise DocumentExtractionError("The document could not be processed.") from error

    if not any(page["text"].strip() for page in pages):
        raise DocumentExtractionError("The document does not contain extractable text.")
    return pages
