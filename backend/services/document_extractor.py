import fitz
import os


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