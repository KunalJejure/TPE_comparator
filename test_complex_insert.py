import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

try:
    supabase = create_client(url, key)
    print("Testing complex JSONB insertion...")
    dummy_result = {
        "job_id": "test-job-123",
        "overall": {"change": "MAJOR", "confidence": 0.95},
        "pages": [{"page": 1, "status": "FAIL", "diff_count": 5}]
    }
    
    test_data = {
        "original_filename": "big_test_orig.pdf",
        "revised_filename": "big_test_rev.pdf",
        "total_pages": 1,
        "status": "FAIL",
        "result_json": dummy_result
    }
    
    res = supabase.table("comparisons").insert(test_data).execute()
    print(f"SUCCESS! Inserted row ID: {res.data[0]['id']}")
except Exception as e:
    print(f"ERROR: {e}")
