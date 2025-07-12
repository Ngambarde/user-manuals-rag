from langchain_community.document_loaders import UnstructuredPDFLoader
from typing import List

def parse_pdf_elements(file_path: str) -> List:
    """
    Parses a PDF document using UnstructuredPDFLoader to extract its
    constituent elements (tables, text, titles, etc.).

    Args:
        file_path: The path to the PDF file.

    Returns:
        A list of 'Document' objects, where each object represents
        a structural element from the PDF.
    """
    print(f"--- Parsing {file_path} ---")
    
    # Use Unstructured to get the elements and their coordinates
    # mode="elements" give fine grained control and metadata like coordinates
    loader = UnstructuredPDFLoader(file_path, mode="elements")
    elements = loader.load()
    
    return elements