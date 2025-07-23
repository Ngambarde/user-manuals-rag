from document_parser import parse_pdf_elements
import os
import sys
import fitz  # PyMuPDF
from collections import defaultdict

sys.path.append(os.path.abspath("src"))

# --- Configuration ---
SOURCE_DIRECTORY = "documents/"
OUTPUT_DIRECTORY = "debug_output/"
COLORS = {
    "Table": (1, 0, 0),
    "NarrativeText": (0, 0, 1),
    "Title": (0, 1, 0),
    "ListItem": (1, 0.5, 0),
    "default": (0.5, 0.5, 0.5),
}


def visualize_pdf_chunks(pdf_path, elements_for_pdf, output_path):
    """
    Visualizes document elements by drawing bounding
    boxes on a copy of the PDF.

    Args:
        pdf_path: Path to the PDF file to visualize.
        elements_for_pdf: List of document elements to visualize.
        output_path: Path to save the annotated PDF.
    """
    print(f"Visualizing {os.path.basename(pdf_path)}...")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Could not open {pdf_path} with PyMuPDF: {e}")
        return

    if len(doc) == 0:
        print("Could not open or is an empty PDF. Skipping.")
        return

    for element in elements_for_pdf:
        metadata = element.metadata
        page_number = metadata.get("page_number")

        if page_number is None or not (1 <= page_number <= len(doc)):
            continue

        page = doc[page_number - 1]

        points = metadata.get("coordinates", {}).get("points")
        if not points:
            continue

        coord_system = metadata.get("coordinates", {}).get("system")
        page_width = page.rect.width
        page_height = page.rect.height

        # --- scaling logic ---
        """
        If strategy = hi_res, the coordinate system is PixelSpace,
        scaling coefficients are applied to correct bounding box positions
        """
        if coord_system == "PixelSpace":
            layout_width = metadata.get("coordinates", {}).get("layout_width")
            layout_height = metadata.get("coordinates", {}).get("layout_height")

            if not layout_width or not layout_height:
                continue

            x_scale = page_width / layout_width
            y_scale = page_height / layout_height

            scaled_points = [(p[0] * x_scale, p[1] * y_scale) for p in points]
            rect = fitz.Rect(scaled_points[0], scaled_points[2])
        else:
            # When strategy="fast", assume native PDF points.
            rect = fitz.Rect(points[0], points[2])

        category = metadata.get("category", "default")
        color = COLORS.get(category, COLORS["default"])

        page.draw_rect(rect, color=color, width=1.5, overlay=True)
        page.insert_text(
            (rect.x0, rect.y0 - 10), f"{category}", fontsize=8, color=color
        )

    print(f"  - Saving annotated file to {output_path}")
    doc.save(output_path)
    doc.close()


if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)
        print(f"Created output directory: {OUTPUT_DIRECTORY}")

    pdf_files_to_process = [
        os.path.join(SOURCE_DIRECTORY, f)
        for f in os.listdir(SOURCE_DIRECTORY)
        if f.lower().endswith(".pdf")
    ]

    if pdf_files_to_process:
        all_elements = parse_pdf_elements(pdf_files_to_process)

        elements_by_file = defaultdict(list)
        for el in all_elements:
            filename = el.metadata.get("filename")
            if filename:
                elements_by_file[os.path.basename(filename)].append(el)

        for source_pdf_path in pdf_files_to_process:
            base_filename = os.path.basename(source_pdf_path)
            output_pdf_path = os.path.join(
                OUTPUT_DIRECTORY, f"{os.path.splitext(base_filename)[0]}_annotated.pdf"
            )

            elements_for_this_pdf = elements_by_file.get(base_filename, [])

            if elements_for_this_pdf:
                visualize_pdf_chunks(
                    source_pdf_path, elements_for_this_pdf, output_pdf_path
                )
            else:
                print(f"No elements found for {base_filename}, skipping visualization.")

    print(f"\n--- Visualization successfully saved to {OUTPUT_DIRECTORY} ---")
