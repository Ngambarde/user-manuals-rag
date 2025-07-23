from langchain_unstructured import UnstructuredLoader
from typing import List


def parse_pdf_elements(file_paths: List[str]) -> List:
    """
    Parses a batch of PDF documents using UnstructuredLoader to extract their
    constituent elements (tables, text, titles, etc.).

    Args:
        file_paths: A list of paths to the PDF files.

    Returns:
        A list of 'Document' objects from all parsed PDFs.
    """
    if not isinstance(file_paths, list):
        raise TypeError("file_paths must be a list of strings.")

    print(f"--- Parsing {len(file_paths)} PDF file(s) in a batch ---")

    loader = UnstructuredLoader(
        file_path=file_paths,
        strategy="hi_res",
        infer_table_structure=True,
    )

    print("Loading models and parsing documents...")
    elements = []
    for element in loader.lazy_load():
        elements.append(element)

    return elements
