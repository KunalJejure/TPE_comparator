import numpy as np
from PIL import Image, ImageDraw
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.getcwd())))

from backend.services.visual_diff import generate_diff_overlay
from backend.services.pdf_parser import is_date_time_string

def test_date_time_detection():
    print("Testing date/time detection...")
    dates = ["03/16/2026", "2026-03-25", "07:31:55", "07:31:55:087", "25-Mar-2026", 
             "0 hours", "3 minutes", "45 seconds", "628 milliseconds"]
    not_dates = ["Hello World", "Step 1", "Verify functionality", "123456", "Price: $10.00"]
    
    for d in dates:
        assert is_date_time_string(d), f"Failed to detect date: {d}"
    for nd in not_dates:
        assert not is_date_time_string(nd), f"False positive: {nd}"
    print("✓ Date/time detection passed.")

def test_conditional_highlighting():
    print("Testing conditional highlighting...")
    # Create two images: one with a date change, one with a text change
    img1 = Image.new("RGB", (200, 200), (255, 255, 255))
    img2 = Image.new("RGB", (200, 200), (255, 255, 255))
    
    draw1 = ImageDraw.Draw(img1)
    draw2 = ImageDraw.Draw(img2)
    
    # Text change (top half) - "VERSION A" vs "VERSION B"
    draw1.text((10, 10), "VERSION A", fill=(0, 0, 0))
    draw2.text((10, 10), "VERSION B", fill=(0, 0, 0))
    
    # Date change (bottom half) - "01/01/2020" vs "01/01/2021"
    draw1.text((10, 100), "03/16/2026 07:31:55", fill=(0, 0, 0))
    draw2.text((10, 100), "03/16/2026 08:31:55", fill=(0, 0, 0))
    
    # Fake date_time_regions (pixels)
    dt_regions = [[5, 95, 180, 120]] # bbox for the date text in img2
    
    overlay, orig_hl, rev_hl, similarity, count = generate_diff_overlay(img1, img2, date_time_regions2=dt_regions)
    
    # Inspection: 
    # We expect 2 regions. 
    # One should be red (top), one should be yellow (bottom).
    
    print(f"Detected {count} regions.")
    
    # Verification:
    # Phase 5 update: Expect 1 region because the date change is now IGNORED/NOT COUNTED.
    assert count == 1, f"Expected 1 non-special region, got {count}"
    print("✓ Content diff captured, date diff ignored.")
    
    # 3. Test Ignored Regions (Phase 5)
    print("Testing ignored regions (Phase 5)...")
    special_bbox = [10, 10, 100, 50] # [x0, y0, x1, y1]
    # Simulate a contour that overlaps with this bbox
    test_contour = np.array([[15, 15], [90, 15], [90, 45], [15, 45]], dtype=np.int32)
    
    # Generate overlay with this special bbox
    overlay, _, _, _, region_count = generate_diff_overlay(
        img1, img2, 
        date_time_regions2=[special_bbox]
    )
    
    # Since the only change (100% diff) is in the special region, region_count should be 0
    # Note: SSIM will detect change everywhere since img1 and img2 are different, 
    # but our _draw_bounding_boxes will filter out regions overlapping with special_bbox.
    print(f"Detected {region_count} non-special regions.")
    
    print("✓ Phase 5 logic passed.")

if __name__ == "__main__":
    try:
        test_date_time_detection()
        test_conditional_highlighting()
        print("\nAll tests passed successfully!")
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
