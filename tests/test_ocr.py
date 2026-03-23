import os
import fitz
from PIL import Image, ImageDraw

def create_image_pdf(filename):
    # Create an image with text
    img = Image.new('RGB', (800, 600), color='white')
    d = ImageDraw.Draw(img)
    d.text((50, 50), "This is a scanned image with hidden text.", fill=(0,0,0))
    img.save("dummy_scan.png")
    
    # Create an image-only PDF
    doc = fitz.open()
    page = doc.new_page(width=800, height=600)
    page.insert_image(page.rect, filename="dummy_scan.png")
    doc.save(filename)
    doc.close()
    
    os.remove("dummy_scan.png")

if __name__ == "__main__":
    pdf_filename = "test_scanned.pdf"
    create_image_pdf(pdf_filename)
    
    from backend.services.pdf_parser import extract_text, extract_structured_text
    
    print("Testing extract_text...")
    text_result = extract_text(pdf_filename)
    print("Result:", text_result)
    
    print("\nTesting extract_structured_text...")
    struct_result = extract_structured_text(pdf_filename)
    print("Result:", struct_result)
    
    os.remove(pdf_filename)
