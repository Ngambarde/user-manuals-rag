import os
import sys
import fitz

sys.path.append(os.path.abspath('src'))
from document_parser import parse_pdf_elements

# --- Configuration ---
SOURCE_DIRECTORY = "documents/"
OUTPUT_DIRECTORY = "debug_output/"
COLORS = {"Table": (1, 0, 0), "NarrativeText": (0, 0, 1), "Title": (0, 1, 0), "ListItem": (1, 0.5, 0), "default": (0.5, 0.5, 0.5)}

def visualize_pdf_chunks(pdf_path, output_path):
    print(f"Visualizing {pdf_path}...")
    
    # --- Using shared function from document_parser.py ---
    elements = parse_pdf_elements(pdf_path)
    
    doc = fitz.open(pdf_path)
    
    if len(doc) == 0:
        print(f"Could not open or is an empty PDF. Skipping.")
        return

    for element in elements:
        metadata = element.metadata
        category = metadata.get('category', 'default')
        page_number = metadata.get('page_number')
        coords = metadata.get('coordinates', {}).get('points')

        if page_number is None or not coords:
            continue

        page = doc[page_number - 1]
        rect = fitz.Rect(coords[0], coords[2])
        color = COLORS.get(category, COLORS["default"])

        page.draw_rect(rect, color=color, width=1.5)
        page.insert_text((rect.x0, rect.y0 - 10), f"{category}", fontsize=8, color=color)

    print(f"Saving annotated file to {output_path}")
    doc.save(output_path)
    doc.close()

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIRECTORY):
        os.makedirs(OUTPUT_DIRECTORY)
        print(f"Created output directory: {OUTPUT_DIRECTORY}")

    for filename in os.listdir(SOURCE_DIRECTORY):
        if filename.lower().endswith(".pdf"):
            source_pdf_path = os.path.join(SOURCE_DIRECTORY, filename)
            output_pdf_path = os.path.join(OUTPUT_DIRECTORY, f"{os.path.splitext(filename)[0]}_annotated.pdf")
            visualize_pdf_chunks(source_pdf_path, output_pdf_path)

    print(f"\n--- Visualization Successfully saved to {OUTPUT_DIRECTORY} ---")